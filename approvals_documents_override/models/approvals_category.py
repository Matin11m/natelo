from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    # In this Odoo 19 stack, folder-like hierarchy is stored on documents.document
    document_type_folder_id = fields.Many2one(
        "documents.document",
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
        help="نوع مدرک از زیرشاخه‌های فولدر «کنترول مستندات» خوانده می‌شود.",
    )
    document_owner_folder_id = fields.Many2one(
        "documents.document",
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
        help="صاحب مدرک از زیرشاخه‌های نوع مدرک انتخاب‌شده خوانده می‌شود.",
    )

    document_type_allowed_ids = fields.Many2many(
        "documents.document",
        compute="_compute_document_folder_domains",
    )
    document_owner_allowed_ids = fields.Many2many(
        "documents.document",
        compute="_compute_document_folder_domains",
    )

    @api.model
    def _documents_folder_model(self):
        return self.env["documents.document"]

    @api.model
    def _documents_parent_field(self):
        folder_model = self._documents_folder_model()
        if "parent_folder_id" in folder_model._fields:
            return "parent_folder_id"
        return "parent_id"

    @api.model
    def _documents_folder_domain(self):
        folder_model = self._documents_folder_model()
        # Keep compatibility with variants where folder records are documents with type='folder'
        if "type" in folder_model._fields:
            return [("type", "=", "folder")]
        return []

    @api.model
    def _get_document_control_root(self):
        """Return the root folder used to feed approval category drop-downs."""
        return self._documents_folder_model().search(
            self._documents_folder_domain() + [("name", "=", "کنترول مستندات")],
            limit=1,
        )

    @api.depends("document_type_folder_id")
    def _compute_document_folder_domains(self):
        folder_obj = self._documents_folder_model()
        parent_field = self._documents_parent_field()
        folder_domain = self._documents_folder_domain()
        root_folder = self._get_document_control_root()

        for rec in self:
            if root_folder:
                rec.document_type_allowed_ids = folder_obj.search(
                    folder_domain + [(parent_field, "=", root_folder.id)]
                )
            else:
                rec.document_type_allowed_ids = folder_obj.browse()

            if rec.document_type_folder_id:
                rec.document_owner_allowed_ids = folder_obj.search(
                    folder_domain + [(parent_field, "=", rec.document_type_folder_id.id)]
                )
            else:
                rec.document_owner_allowed_ids = folder_obj.browse()

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        parent_field = self._documents_parent_field()
        folder_domain = self._documents_folder_domain()

        self.document_owner_folder_id = False
        if not self.document_type_folder_id:
            return {
                "domain": {
                    "document_owner_folder_id": [("id", "=", False)],
                }
            }

        return {
            "domain": {
                "document_owner_folder_id": folder_domain
                + [(parent_field, "=", self.document_type_folder_id.id)],
            }
        }
