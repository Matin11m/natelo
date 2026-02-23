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
        """Keep user-defined done date after Odoo finalization."""
        saved_dates = {picking.id: picking.date_done for picking in self}
        res = super()._action_done()
        for picking in self:
            if saved_dates.get(picking.id):
                picking.date_done = saved_dates[picking.id]
        return res

    def button_validate(self):
        _logger.info("========== CUSTOM VALIDATION START ==========")

        # Debug helper when needed (disabled by default)
        if self.env.context.get("debug_show_done_date"):
            raise UserError(_("%s") % (self.date_done or "-"))

        for picking in self:
            _logger.info("[PICKING] %s", picking.name)
            picking._check_negative_stock_balance()

        res = super().button_validate()

        # Only sync records really finalized.
        for picking in self.filtered(lambda p: p.state == "done"):
            picking._update_effective_date()

        _logger.info("========== CUSTOM VALIDATION END ==========")
        return res

    def _get_effective_date(self):
        self.ensure_one()
        if self.effective_date_time:
            return self.effective_date_time
        if "x_studio_effective_date_time" in self._fields and self.x_studio_effective_date_time:
            return self.x_studio_effective_date_time
        return self.date_done

    def _update_effective_date(self):
        """Update done dates/locations on related done moves and move lines."""
        self.ensure_one()
        effective_date = self._get_effective_date()
        if not effective_date:
            return

        done_moves = self.move_ids.filtered(lambda m: m.state == "done")
        vals = {
            "date": effective_date,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
        }
        done_moves.write(vals)
        done_moves.mapped("move_line_ids").write(vals)
        self.date_done = effective_date

    def _sort_key_for_location(self, move, location_id):
        date_part = (move.date or move.create_date).date()
        priority = 1 if move.location_dest_id.id == location_id else 2
        return (date_part, priority, move.id)

    def _check_negative_stock_balance(self):
        """Historical cumulative balance check before validate."""
        self.ensure_one()

        excluded_location_ids = {14, 15, 96}
        usage_exclusions = {"supplier", "view", "customer", "production"}

        current_moves = self.move_ids.filtered(
            lambda m: m.state != "cancel" and m.product_id.is_storable
        )
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
                _logger.info(
                    "[PROCESS] Product: %s | Location ID: %s",
                    product.display_name,
                    location_id,
                )

                domain = [
                    ("state", "=", "done"),
                    ("product_id", "=", product.id),
                    "|",
                    ("location_id", "=", location_id),
                    ("location_dest_id", "=", location_id),
                ]
                past_moves = self.env["stock.move"].search(domain)

                relevant_current = current_moves.filtered(lambda m: m.product_id == product)
                all_moves = (past_moves | relevant_current).sorted(
                    key=lambda m: self._sort_key_for_location(m, location_id)
                )

                balance = 0.0
                for move in all_moves:
                    qty = move.quantity
                    if move.product_uom.factor:
                        qty_in_product_uom = qty / move.product_uom.factor
                    else:
                        qty_in_product_uom = qty

                    if move.location_dest_id.id == location_id:
                        qty_in_product_uom = float("%.7f" % qty_in_product_uom)
                        balance += qty_in_product_uom
                        direction = "IN"
                    elif move.location_id.id == location_id:
                        qty_in_product_uom = float("%.6f" % qty_in_product_uom)
                        balance -= qty_in_product_uom
                        direction = "OUT"
                    else:
                        continue

                    _logger.info(
                        "[MOVE] %s | %s | Qty: %s | Balance: %s",
                        move.reference or move.id,
                        direction,
                        qty_in_product_uom,
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
                                "• کالا: %s\n"
                                "• انبار: %s\n"
                                "• تاریخ: %s\n"
                                "• موجودی جدید: %s"
                            )
                            % (
                                product.display_name,
                                location.complete_name,
                                (move.date or move.create_date).date(),
                                balance,
                            )
                        )
