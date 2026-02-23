# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    effective_date_time = fields.Datetime(
        string="Effective Date",
        help="When set, this date is used as done date for the picking and as the date "
        "for related stock moves and move lines at validation time.",
    )

    def _action_done(self):
        """Preserve user-set done date across Odoo finalization."""
        saved_dates = {picking.id: picking.date_done for picking in self}
        res = super()._action_done()
        for picking in self:
            saved_date = saved_dates.get(picking.id)
            if saved_date:
                picking.date_done = saved_date
        return res

    def button_validate(self):
        """Validate picking with pre-check and post-sync hooks."""
        _logger.info("========== CUSTOM VALIDATION START ==========")

        # Optional fast debug helper (disabled by default).
        if self.env.context.get("debug_show_done_date"):
            raise UserError(_("%s") % (self.date_done or "-"))

        for picking in self:
            _logger.info("[PICKING] %s", picking.name)
            picking._check_negative_stock_balance()

        res = super().button_validate()

        for picking in self.filtered(lambda p: p.state == "done"):
            picking._update_effective_date()

        _logger.info("========== CUSTOM VALIDATION END ==========")
        return res

    def _update_effective_date(self):
        """Push selected effective date to done moves and move lines."""
        self.ensure_one()
        effective_date = self.effective_date_time or self.date_done
        if not effective_date:
            return

        done_moves = self.move_ids.filtered(lambda m: m.state == "done")
        done_moves.write(
            {
                "date": effective_date,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
            }
        )

        done_moves.mapped("move_line_ids").write(
            {
                "date": effective_date,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
            }
        )

        self.write({"date_done": effective_date})

    def _check_negative_stock_balance(self):
        """Historical negative-stock check before validation."""
        self.ensure_one()

        excluded_location_ids = {14, 15, 96}
        usage_exclusions = {"supplier", "view", "customer", "production"}
        current_moves = self.move_ids.filtered(lambda m: m.state != "cancel" and m.product_id.is_storable)

        products = current_moves.mapped("product_id")
        locations = set()

        for move in current_moves:
            for loc in (move.location_id, move.location_dest_id):
                if (
                    loc
                    and loc.usage not in usage_exclusions
                    and loc.id not in excluded_location_ids
                    and not loc.allow_negative_stock
                ):
                    locations.add(loc.id)

        _logger.info("[CHECK] Products: %s", [p.display_name for p in products])
        _logger.info("[CHECK] Locations: %s", list(locations))

        for product in products:
            if product.allow_negative_stock or product.categ_id.allow_negative_stock:
                continue

            for location_id in locations:
                _logger.info("[PROCESS] Product: %s | Location ID: %s", product.display_name, location_id)

                past_moves = self.env["stock.move"].search(
                    [
                        ("state", "=", "done"),
                        ("product_id", "=", product.id),
                        "|",
                        ("location_id", "=", location_id),
                        ("location_dest_id", "=", location_id),
                    ],
                    order="date asc, id asc",
                )

                relevant_current = current_moves.filtered(lambda m: m.product_id == product)
                all_moves = past_moves | relevant_current

                balance = 0.0
                for move in all_moves.sorted(lambda m: m.date or m.create_date):
                    qty = move.product_uom._compute_quantity(
                        move.quantity or move.product_uom_qty,
                        move.product_id.uom_id,
                        rounding_method="HALF-UP",
                    )

                    if move.location_dest_id.id == location_id:
                        balance += qty
                        direction = "IN"
                    elif move.location_id.id == location_id:
                        balance -= qty
                        direction = "OUT"
                    else:
                        continue

                    _logger.info(
                        "[MOVE] %s | %s | Qty: %s | Balance: %s",
                        move.reference or move.id,
                        direction,
                        qty,
                        balance,
                    )

                    if balance < -0.0000001:
                        location = self.env["stock.location"].browse(location_id)
                        _logger.error(
                            "NEGATIVE DETECTED -> %s | %s | Balance: %s",
                            product.display_name,
                            location.complete_name,
                            balance,
                        )
                        raise UserError(
                            _(
                                "موجودی منفی شناسایی شد:\n\n"
                                "کالا: %s\n"
                                "انبار: %s\n"
                                "موجودی: %s"
                            )
                            % (product.display_name, location.complete_name, balance)
                        )
