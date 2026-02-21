from odoo import api, fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    document_type_folder_id = fields.Many2one(
        "documents.document",
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
    )
    document_owner_folder_id = fields.Many2one(
        "documents.document",
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
    )

    document_type_allowed_ids = fields.Many2many(
        "documents.document",
        compute="_compute_document_allowed_ids",
    )
    document_owner_allowed_ids = fields.Many2many(
        "documents.document",
        compute="_compute_document_allowed_ids",
    )

    @api.model
    def _documents_parent_field(self):
        folder_model = self.env["documents.document"]
        for field_name in ("parent_folder_id", "parent_id", "folder_id"):
            if field_name in folder_model._fields:
                return field_name
        return "parent_id"

    @api.depends("category_id", "document_type_folder_id")
    def _compute_document_allowed_ids(self):
        folder_obj = self.env["documents.document"]
        parent_field = self._documents_parent_field()
        for rec in self:
            rec.document_type_allowed_ids = rec.category_id.document_type_allowed_ids
            if rec.document_type_folder_id:
                rec.document_owner_allowed_ids = folder_obj.search(
                    [(parent_field, "=", rec.document_type_folder_id.id)]
                )
            else:
                rec.document_owner_allowed_ids = folder_obj.browse()

    @api.onchange("category_id")
    def _onchange_category_id_document_defaults(self):
        self.document_type_folder_id = self.category_id.document_type_folder_id
        self.document_owner_folder_id = self.category_id.document_owner_folder_id

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        self.document_owner_folder_id = False
        if not self.document_type_folder_id:
            return {"domain": {"document_owner_folder_id": [("id", "=", False)]}}

        parent_field = self._documents_parent_field()
        return {
            "domain": {
                "document_owner_folder_id": [
                    (parent_field, "=", self.document_type_folder_id.id)
                ],
            }
        }
