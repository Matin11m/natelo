# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError


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
                picking.with_context(allow_done_date_write=True).date_done = saved_dates[picking.id]
        return res

    def write(self, vals):
        if "date_done" in vals and not self.env.context.get("allow_done_date_write"):
            done_pickings = self.filtered(lambda p: p.state == "done")
            if done_pickings:
                raise UserError(
                    self.env._("You cannot modify Done Date after the picking is validated.")
                )
        return super().write(vals)
