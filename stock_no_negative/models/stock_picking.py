# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    effective_date_time = fields.Datetime(
        string="Effective Date",
        help="When set, this date is used as done date for the picking and as the date "
        "for related stock moves and move lines at validation time.",
    )

    def _action_done(self):
        """Preserve user-set done date after Odoo finalization."""
        saved_dates = {picking.id: picking.date_done for picking in self}
        res = super()._action_done()
        for picking in self:
            if saved_dates.get(picking.id):
                picking.date_done = saved_dates[picking.id]
        return res
