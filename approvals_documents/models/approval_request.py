from odoo import api, fields, models


class ApprovalRequest(models.Model):
    """Allow request users to select type/owner from category-scoped Documents data."""

    _inherit = "approval.request"

    _DOCUMENT_MODEL = "documents.document"
    _PARENT_CANDIDATE_FIELDS = ("parent_folder_id", "parent_id", "folder_id")

    category_document_fields_visibility = fields.Selection(
        related="category_id.document_fields_visibility",
        readonly=True,
    )

    document_type_folder_id = fields.Many2one(
        _DOCUMENT_MODEL,
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
    )
    document_owner_folder_id = fields.Many2one(
        _DOCUMENT_MODEL,
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
    )

    document_type_allowed_ids = fields.Many2many(
        _DOCUMENT_MODEL,
        compute="_compute_document_allowed_ids",
    )
    document_owner_allowed_ids = fields.Many2many(
        _DOCUMENT_MODEL,
        compute="_compute_document_allowed_ids",
    )

    @api.model
    def _documents_parent_field(self):
        """Resolve parent field name for Documents hierarchy across versions."""
        folder_model = self.env[self._DOCUMENT_MODEL]
        for field_name in self._PARENT_CANDIDATE_FIELDS:
            if field_name in folder_model._fields:
                return field_name
        return "parent_id"

    @api.depends("category_id", "document_type_folder_id", "category_document_fields_visibility")
    def _compute_document_allowed_ids(self):
        """Compute request-level allowed options based on category setup and type."""
        folder_model = self.env[self._DOCUMENT_MODEL]
        parent_field = self._documents_parent_field()

        for rec in self:
            is_enabled = rec.category_document_fields_visibility != "none"
            rec.document_type_allowed_ids = (
                rec.category_id.document_type_allowed_ids if is_enabled else folder_model.browse()
            )
            rec.document_owner_allowed_ids = (
                folder_model.search([(parent_field, "=", rec.document_type_folder_id.id)])
                if is_enabled and rec.document_type_folder_id
                else folder_model.browse()
            )

    @api.onchange("category_id")
    def _onchange_category_id_document_defaults(self):
        """Reset selections and scope domains to category-allowed data."""
        self.document_type_folder_id = False
        self.document_owner_folder_id = False

        if self.category_document_fields_visibility == "none":
            return {
                "domain": {
                    "document_type_folder_id": [("id", "=", False)],
                    "document_owner_folder_id": [("id", "=", False)],
                }
            }

        allowed_type_ids = self.category_id.document_type_allowed_ids.ids
        return {
            "domain": {
                "document_type_folder_id": [("id", "in", allowed_type_ids)],
                "document_owner_folder_id": [("id", "=", False)],
            }
        }

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        """Reset and filter owner list whenever type changes."""
        self.document_owner_folder_id = False
        if self.category_document_fields_visibility == "none" or not self.document_type_folder_id:
            return {"domain": {"document_owner_folder_id": [("id", "=", False)]}}

        parent_field = self._documents_parent_field()
        return {
            "domain": {
                "document_owner_folder_id": [(parent_field, "=", self.document_type_folder_id.id)],
            }
        }
