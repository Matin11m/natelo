from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    # Odoo 19 Documents folder model
    document_type_folder_id = fields.Many2one(
        "documents.project",
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
        help="نوع مدرک از زیرشاخه‌های فولدر «کنترول مستندات» خوانده می‌شود.",
    )
    document_owner_folder_id = fields.Many2one(
        "documents.project",
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
        help="صاحب مدرک از زیرشاخه‌های نوع مدرک انتخاب‌شده خوانده می‌شود.",
    )

    document_type_allowed_ids = fields.Many2many(
        "documents.project",
        compute="_compute_document_folder_domains",
    )
    document_owner_allowed_ids = fields.Many2many(
        "documents.project",
        compute="_compute_document_folder_domains",
    )

    @api.model
    def _documents_folder_model(self):
        return self.env["documents.project"]

    @api.model
    def _documents_parent_field(self):
        folder_model = self._documents_folder_model()
        if "parent_folder_id" in folder_model._fields:
            return "parent_folder_id"
        return "parent_id"

    @api.model
    def _get_document_control_root(self):
        """Return the root folder used to feed approval category drop-downs."""
        return self._documents_folder_model().search(
            [("name", "=", "کنترول مستندات")],
            limit=1,
        )

    @api.depends("document_type_folder_id")
    def _compute_document_folder_domains(self):
        folder_obj = self._documents_folder_model()
        parent_field = self._documents_parent_field()
        root_folder = self._get_document_control_root()

        for rec in self:
            if root_folder:
                rec.document_type_allowed_ids = folder_obj.search(
                    [(parent_field, "=", root_folder.id)]
                )
            else:
                rec.document_type_allowed_ids = folder_obj.browse()

            if rec.document_type_folder_id:
                rec.document_owner_allowed_ids = folder_obj.search(
                    [(parent_field, "=", rec.document_type_folder_id.id)]
                )
            else:
                rec.document_owner_allowed_ids = folder_obj.browse()

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        parent_field = self._documents_parent_field()

        if not self.document_type_folder_id:
            self.document_owner_folder_id = False
            return {
                "domain": {
                    "document_owner_folder_id": [("id", "=", False)],
                }
            }

        self.document_owner_folder_id = False
        return {
            "domain": {
                "document_owner_folder_id": [
                    (parent_field, "=", self.document_type_folder_id.id)
                ],
            }
        }
