# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    _EXCLUDED_LOCATION_IDS = {14, 15, 96}
    _USAGE_EXCLUSIONS = {"supplier", "view", "customer", "production"}
    _BALANCE_FLOOR = -0.0000001

    def _action_done(self, cancel_backorder=False):
        candidate_moves = self.filtered(lambda m: m.state != "done" and m.product_id.is_storable)
        if candidate_moves:
            self._prepare_moves_from_picking(candidate_moves)
            self._check_negative_stock_history(candidate_moves)

        res = super()._action_done(cancel_backorder=cancel_backorder)

        if candidate_moves:
            self._apply_picking_dates_after_done(candidate_moves)
        return res

    def _prepare_moves_from_picking(self, moves):
        for picking in moves.filtered("picking_id").mapped("picking_id"):
            if not picking.date_done:
                raise UserError(self.env._("تاریخ برگه نمی‌تواند خالی باشد."))

            picking_moves = moves.filtered(lambda m: m.picking_id == picking)
            vals = {
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
            picking_moves.write(vals)
            picking_moves.mapped("move_line_ids").write(
                {
                    "date": picking.date_done,
                    **vals,
                }
            )
            _logger.info(
                "[MOVE_PREP] picking=%s moves=%s move_lines=%s date_done=%s",
                picking.name,
                len(picking_moves),
                len(picking_moves.mapped("move_line_ids")),
                picking.date_done,
            )

    def _apply_picking_dates_after_done(self, moves):
        done_moves = moves.filtered(lambda m: m.state == "done" and m.picking_id)
        for picking in done_moves.mapped("picking_id"):
            picking_moves = done_moves.filtered(lambda m: m.picking_id == picking)
            if not picking.date_done:
                continue
            picking_moves.write({"date": picking.date_done})
            picking_moves.mapped("move_line_ids").write({"date": picking.date_done})
            _logger.info(
                "[MOVE_POST] picking=%s done_moves=%s done_move_lines=%s date_done=%s",
                picking.name,
                len(picking_moves),
                len(picking_moves.mapped("move_line_ids")),
                picking.date_done,
            )

    def _sort_key(self, move, location_id):
        move_date = (move.date or move.create_date).date()
        priority = 1 if move.location_dest_id.id == location_id else 2
        return (move_date, priority, move.id)

    def _check_negative_stock_history(self, moves):
        move_model = self.env["stock.move"]

        for picking in moves.filtered("picking_id").mapped("picking_id"):
            current_moves = moves.filtered(lambda m: m.picking_id == picking)
            products = current_moves.mapped("product_id")

            locations = set()
            for move in current_moves:
                for location in (move.location_id, move.location_dest_id):
                    if (
                        location.usage not in self._USAGE_EXCLUSIONS
                        and location.id not in self._EXCLUDED_LOCATION_IDS
                        and not location.allow_negative_stock
                    ):
                        locations.add(location.id)

            _logger.info(
                "[NEG_CHECK][START] picking=%s products=%s locations=%s",
                picking.name,
                [p.display_name for p in products],
                sorted(locations),
            )

            for product in products:
                if product.allow_negative_stock or product.categ_id.allow_negative_stock:
                    _logger.info("[NEG_CHECK][SKIP] product=%s allow_negative enabled", product.display_name)
                    continue

                for location_id in locations:
                    domain = [
                        ("state", "=", "done"),
                        ("product_id", "=", product.id),
                        "|",
                        ("location_id", "=", location_id),
                        ("location_dest_id", "=", location_id),
                    ]
                    done_moves = move_model.search(domain)
                    current_product_moves = current_moves.filtered(lambda m: m.product_id == product)
                    unique_moves = done_moves | current_product_moves
                    sorted_moves = unique_moves.sorted(key=lambda m: self._sort_key(m, location_id))

                    _logger.info(
                        "[NEG_CHECK][SCOPE] picking=%s product=%s location_id=%s done=%s current=%s total=%s",
                        picking.name,
                        product.display_name,
                        location_id,
                        len(done_moves),
                        len(current_product_moves),
                        len(sorted_moves),
                    )

                    balance = 0.0
                    for move in sorted_moves:
                        qty = move.quantity or move.product_uom_qty
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
                            "[NEG_CHECK][MOVE] pick=%s ref=%s id=%s date=%s dir=%s qty=%s balance=%s",
                            picking.name,
                            move.reference or "-",
                            move.id,
                            move.date,
                            direction,
                            qty_in_product_uom,
                            balance,
                        )

                        if balance < self._BALANCE_FLOOR:
                            location = self.env["stock.location"].browse(location_id)
                            _logger.error(
                                "[NEG_CHECK][NEGATIVE] pick=%s product=%s location=%s date=%s qty=%s balance=%s",
                                picking.name,
                                product.display_name,
                                location.complete_name,
                                (move.date or move.create_date).date(),
                                qty_in_product_uom,
                                balance,
                            )
                            raise UserError(
                                self.env._(
                                    "موجودی منفی شناسایی شد:\n\n"
                                    "• کالا: %(product)s\n"
                                    "• انبار: %(location)s\n"
                                    "• تاریخ: %(date)s\n"
                                    "• مقدار حرکت: %(qty)s\n"
                                    "• موجودی جدید: %(balance)s",
                                    product=product.display_name,
                                    location=location.complete_name,
                                    date=(move.date or move.create_date).date(),
                                    qty=qty_in_product_uom,
                                    balance=balance,
                                )
                            )

                    _logger.info(
                        "[NEG_CHECK][RESULT] picking=%s product=%s location_id=%s final_balance=%s",
                        picking.name,
                        product.display_name,
                        location_id,
                        balance,
                    )
