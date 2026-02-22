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
