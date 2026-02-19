from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    document_type_folder_id = fields.Many2one(
        "documents.document",
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
        help="نوع مدرک از فولدرهای «کنترول مستندات» و شاخه‌های آن خوانده می‌شود.",
    )
    document_owner_folder_id = fields.Many2one(
        "documents.document",
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
        help="صاحب مدرک از زیرمجموعه‌های نوع مدرک انتخاب‌شده خوانده می‌شود.",
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
        for field_name in ("parent_folder_id", "parent_id", "folder_id"):
            if field_name in folder_model._fields:
                return field_name
        return "parent_id"

    @api.model
    def _get_document_control_roots(self):
        """Find all roots named exactly 'کنترول مستندات' across Documents."""
        return self._documents_folder_model().search([("name", "=", "کنترول مستندات")])

    @api.model
    def _children_of(self, parents):
        """Return direct children of one record or a recordset."""
        if not parents:
            return self._documents_folder_model().browse()

        parent_field = self._documents_parent_field()
        return self._documents_folder_model().search([(parent_field, "in", parents.ids)])

    @api.depends("document_type_folder_id")
    def _compute_document_folder_domains(self):
        folder_obj = self._documents_folder_model()
        control_roots = self._get_document_control_roots()
        type_nodes = self._children_of(control_roots)

        for rec in self:
            rec.document_type_allowed_ids = type_nodes
            rec.document_owner_allowed_ids = (
                self._children_of(rec.document_type_folder_id)
                if rec.document_type_folder_id
                else folder_obj.browse()
            )

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        self.document_owner_folder_id = False
        if not self.document_type_folder_id:
            return {"domain": {"document_owner_folder_id": [("id", "=", False)]}}

        owner_ids = self._children_of(self.document_type_folder_id).ids
        return {
            "domain": {
                "document_owner_folder_id": [("id", "in", owner_ids)],
            }
        }
