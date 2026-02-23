# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    _NEGATIVE_HISTORY_EXCLUDED_USAGES = {"supplier", "view", "customer", "production"}
    _NEGATIVE_HISTORY_EXCLUDED_LOCATION_IDS = {14, 15, 96}
    _NEGATIVE_HISTORY_BALANCE_FLOOR = -0.0000001

    def _action_done(self, cancel_backorder=False):
        candidate_moves = self.filtered(lambda m: m.state != "done" and m.product_id.is_storable)
        effective_by_picking = self._get_effective_date_by_picking(candidate_moves)
        self._sync_locations_from_picking(candidate_moves)
        self._check_negative_stock_history_on_done_candidates(candidate_moves, effective_by_picking)
        res = super()._action_done(cancel_backorder=cancel_backorder)
        self._apply_effective_dates_after_done(effective_by_picking)
        return res

    def _get_effective_date_by_picking(self, candidate_moves):
        """Return {picking: effective_date} for pickings that define one.

        We keep compatibility with environments that may not always set an
        explicit effective date. In those cases we simply skip overriding dates
        instead of blocking validation.
        """
        effective_by_picking = {}
        for picking in candidate_moves.filtered("picking_id").mapped("picking_id"):
            effective_date = picking.effective_date_time
            if not effective_date and "x_studio_effective_date_time" in picking._fields:
                effective_date = picking.x_studio_effective_date_time
            if not effective_date:
                effective_date = picking.date_done
            if not effective_date:
                continue
            effective_by_picking[picking] = effective_date
        return effective_by_picking

    def _sync_locations_from_picking(self, candidate_moves):
        """Align move and move-line locations with their picking before validation."""
        moves_with_picking = candidate_moves.filtered("picking_id")
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
        """Re-apply effective date fields after done to prevent Odoo overrides."""
        if not effective_by_picking:
            return

        done_moves = self.filtered(lambda m: m.state == "done" and m.picking_id)
        for picking, effective_date in effective_by_picking.items():
            picking_done_moves = done_moves.filtered(lambda m: m.picking_id == picking)
            if not picking_done_moves:
                continue
            picking.write({"date_done": effective_date, "effective_date_time": effective_date})
            picking_done_moves.write({"date": effective_date})
            picking_done_moves.mapped("move_line_ids").write({"date": effective_date})

    def _historical_sort_key(self, move, location_id, effective_by_picking):
        move_date = effective_by_picking.get(move.picking_id, move.date)
        date_part = move_date.date()
        priority = 1 if move.location_dest_id.id == location_id else 2
        return (date_part, priority, move.id)

    def _get_move_qty_in_product_uom(self, move, location_id):
        qty = move.quantity
        if move.product_uom.factor:
            qty_in_product_uom = qty / move.product_uom.factor
        else:
            qty_in_product_uom = qty

        if move.location_dest_id.id == location_id:
            return float("%.7f" % qty_in_product_uom), 1
        return float("%.6f" % qty_in_product_uom), -1

    def _check_negative_stock_history_on_done_candidates(self, candidate_moves, effective_by_picking):
        """Historical negative stock check including moves being completed now."""
        if not candidate_moves:
            return

        product_ids = set(candidate_moves.mapped("product_id").ids)
        location_ids = {
            loc.id
            for loc in (candidate_moves.mapped("location_id") | candidate_moves.mapped("location_dest_id"))
            if (
                loc.usage not in self._NEGATIVE_HISTORY_EXCLUDED_USAGES
                and not loc.allow_negative_stock
                and loc.id not in self._NEGATIVE_HISTORY_EXCLUDED_LOCATION_IDS
            )
        }
        if not product_ids or not location_ids:
            return

        product_model = self.env["product.product"]
        move_model = self.env["stock.move"]

        for product in product_model.browse(product_ids):
            if product.allow_negative_stock or product.categ_id.allow_negative_stock:
                continue

            current_product_moves = candidate_moves.filtered(lambda m: m.product_id == product)
            if not current_product_moves:
                continue

            done_product_moves = move_model.search(
                [
                    ("state", "=", "done"),
                    ("product_id", "=", product.id),
                    "|",
                    ("location_id", "in", list(location_ids)),
                    ("location_dest_id", "in", list(location_ids)),
                ]
            )
            unique_moves = done_product_moves | current_product_moves

            balances = defaultdict(float)
            for location_id in location_ids:
                sorted_moves = sorted(
                    unique_moves,
                    key=lambda move: self._historical_sort_key(move, location_id, effective_by_picking),
                )
                balances[location_id] = 0.0

                for move in sorted_moves:
                    if location_id not in (move.location_id.id, move.location_dest_id.id):
                        continue

                    qty_in_product_uom, sign = self._get_move_qty_in_product_uom(move, location_id)
                    balances[location_id] += sign * qty_in_product_uom

                    if balances[location_id] < self._NEGATIVE_HISTORY_BALANCE_FLOOR:
                        location = self.env["stock.location"].browse(location_id)
                        move_date = effective_by_picking.get(move.picking_id, move.date)
                        raise UserError(
                            self.env._(
                                "موجودی منفی شناسایی شد:\n\n"
                                "• کالا: %(product)s\n"
                                "• انبار: %(location)s\n"
                                "• تاریخ: %(date)s\n"
                                "• مقدار حرکت: %(qty)s\n"
                                "• موجودی جدید: %(balance)s",
                                product=move.product_id.display_name,
                                location=location.complete_name,
                                date=move_date.date(),
                                qty=qty_in_product_uom,
                                balance=balances[location_id],
                            )
                        )
