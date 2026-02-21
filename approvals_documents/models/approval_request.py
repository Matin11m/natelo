from odoo import api, fields, models


class ApprovalRequest(models.Model):
    """Allow request users to select type/owner from category-scoped Documents data."""

    _inherit = "approval.request"

    _DOCUMENT_MODEL = "documents.document"
    _PARENT_CANDIDATE_FIELDS = ("parent_folder_id", "parent_id", "folder_id")

    _sql_constraints = [
        (
            "approval_request_number_unique",
            "unique(request_number)",
            "Request Number must be unique.",
        )
    ]

    request_number = fields.Char(
        string="شماره درخواست",
        copy=False,
        readonly=True,
        default="New",
        index=True,
    )

    category_type_degree = fields.Selection(
        related="category_id.type_degree",
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

    @api.model_create_multi
    def create(self, vals_list):
        """Assign a unique request number at create time using ir.sequence."""
        for vals in vals_list:
            if not vals.get("request_number") or vals.get("request_number") == "New":
                vals["request_number"] = self.env["ir.sequence"].next_by_code(
                    "approvals_documents.request_number"
                ) or "New"
        return super().create(vals_list)

    @api.model
    def _documents_parent_field(self):
        """Resolve parent field name for Documents hierarchy across versions."""
        folder_model = self.env[self._DOCUMENT_MODEL]
        for field_name in self._PARENT_CANDIDATE_FIELDS:
            if field_name in folder_model._fields:
                return field_name
        return "parent_id"

    @api.depends("category_id", "document_type_folder_id", "category_type_degree")
    def _compute_document_allowed_ids(self):
        """Compute request-level allowed options based on category setup and type."""
        folder_model = self.env[self._DOCUMENT_MODEL]
        parent_field = self._documents_parent_field()

        for rec in self:
            is_enabled = rec.category_type_degree != "none"
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

        if self.category_type_degree == "none":
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
        if self.category_type_degree == "none" or not self.document_type_folder_id:
            return {"domain": {"document_owner_folder_id": [("id", "=", False)]}}

        parent_field = self._documents_parent_field()
        return {
            "domain": {
                "document_owner_folder_id": [(parent_field, "=", self.document_type_folder_id.id)],
            }
        }
