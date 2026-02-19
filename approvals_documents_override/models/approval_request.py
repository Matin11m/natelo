from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    document_type_folder_id = fields.Many2one(
        "documents.document",
        string="نوع مدرک",
        related="category_id.document_type_folder_id",
        store=True,
        readonly=True,
    )
    document_owner_folder_id = fields.Many2one(
        "documents.document",
        string="صاحب مدرک",
        related="category_id.document_owner_folder_id",
        store=True,
        readonly=True,
    )
