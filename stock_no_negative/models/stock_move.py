# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        effective_by_picking = self._get_effective_date_by_picking()
        self._sync_locations_from_picking()
        res = super()._action_done(cancel_backorder=cancel_backorder)
        self._apply_effective_dates_after_done(effective_by_picking)
        self._check_negative_stock_history()
        return res

    def _get_effective_date_by_picking(self):
        """Return {picking: effective_date} for pickings that define one."""
        effective_by_picking = {}
        for picking in self.filtered("picking_id").mapped("picking_id"):
            effective_date = picking.effective_date_time
            if not effective_date and "x_studio_effective_date_time" in picking._fields:
                # Backward-compatible fallback for existing Studio deployments.
                effective_date = picking.x_studio_effective_date_time
            if effective_date:
                effective_by_picking[picking] = effective_date
        return effective_by_picking

    def _sync_locations_from_picking(self):
        """Align move/move-line locations with their picking before validation."""
        moves_with_picking = self.filtered("picking_id")
        if not moves_with_picking:
            return

        for picking in moves_with_picking.mapped("picking_id"):
            picking_moves = moves_with_picking.filtered(lambda m: m.picking_id == picking)
            vals = {
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
            picking_moves.write(vals)
            picking_moves.mapped("move_line_ids").write(vals)

    def _apply_effective_dates_after_done(self, effective_by_picking):
        """Re-apply effective date after done to prevent Odoo overrides."""
        if not effective_by_picking:
            return

        done_moves = self.filtered(lambda m: m.state == "done" and m.picking_id)
        for picking, effective_date in effective_by_picking.items():
            picking_done_moves = done_moves.filtered(lambda m: m.picking_id == picking)
            if not picking_done_moves:
                continue
            picking.write({"date_done": effective_date})
            picking_done_moves.write({"date": effective_date})
            picking_done_moves.mapped("move_line_ids").write({"date": effective_date})

    def _check_negative_stock_history(self):
        """Historical negative stock check across done moves.

        This complements quant-level checks by validating chronological balance
        evolution per (product, location) and catches back-dated inconsistencies.
        """
        done_moves = self.filtered(lambda m: m.state == "done" and m.product_id.is_storable)
        if not done_moves:
            return

        excluded_usage = {"supplier", "view", "customer", "production"}
        balance_floor = -0.0000001

        # Build scope once: products and locations touched by current moves.
        product_ids = set(done_moves.mapped("product_id").ids)
        relevant_location_ids = {
            loc.id
            for loc in (done_moves.mapped("location_id") | done_moves.mapped("location_dest_id"))
            if loc.usage not in excluded_usage and not loc.allow_negative_stock
        }
        if not product_ids or not relevant_location_ids:
            return

        product_model = self.env["product.product"]
        move_model = self.env["stock.move"]

        for product in product_model.browse(product_ids):
            if product.allow_negative_stock or product.categ_id.allow_negative_stock:
                continue

            # Single ordered query per product (instead of per product/location pair).
            product_moves = move_model.search(
                [
                    ("state", "=", "done"),
                    ("product_id", "=", product.id),
                    "|",
                    ("location_id", "in", list(relevant_location_ids)),
                    ("location_dest_id", "in", list(relevant_location_ids)),
                ],
                order="date asc, id asc",
            )

            balances = defaultdict(float)
            for move in product_moves:
                src = move.location_id
                dst = move.location_dest_id
                qty = move.product_uom._compute_quantity(
                    move.quantity,
                    move.product_id.uom_id,
                    rounding_method="HALF-UP",
                )

                if src.id in relevant_location_ids and src.usage not in excluded_usage:
                    balances[src.id] -= qty
                    if balances[src.id] < balance_floor:
                        raise UserError(
                            self.env._(
                                "موجودی منفی شناسایی شد:\n\n"
                                "• کالا: %(product)s\n"
                                "• انبار: %(location)s\n"
                                "• تاریخ: %(date)s\n"
                                "• مقدار حرکت: %(qty)s\n"
                                "• موجودی جدید: %(balance)s",
                                product=move.product_id.display_name,
                                location=src.complete_name,
                                date=move.date.date(),
                                qty=qty,
                                balance=balances[src.id],
                            )
                        )

                if dst.id in relevant_location_ids and dst.usage not in excluded_usage:
                    balances[dst.id] += qty
                    if balances[dst.id] < balance_floor:
                        raise UserError(
                            self.env._(
                                "موجودی منفی شناسایی شد:\n\n"
                                "• کالا: %(product)s\n"
                                "• انبار: %(location)s\n"
                                "• تاریخ: %(date)s\n"
                                "• مقدار حرکت: %(qty)s\n"
                                "• موجودی جدید: %(balance)s",
                                product=move.product_id.display_name,
                                location=dst.complete_name,
                                date=move.date.date(),
                                qty=qty,
                                balance=balances[dst.id],
                            )
                        )
