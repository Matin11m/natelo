from odoo import api, fields, models


class ApprovalCategory(models.Model):
    """Extend approval.category with Documents field policy and allowed type source."""

    _inherit = "approval.category"

    _DOCUMENT_MODEL = "documents.document"
    _CONTROL_ROOT_NAME = "کنترل مستندات"
    _PARENT_CANDIDATE_FIELDS = ("parent_folder_id", "parent_id", "folder_id")
    _DISPLAY_SELECTION = [
        ("none", "None"),
        ("optional", "Optional"),
        ("required", "Required"),
    ]

    document_type_visibility = fields.Selection(
        _DISPLAY_SELECTION,
        string="نوع مدرک",
        default="optional",
        required=True,
    )
    document_owner_visibility = fields.Selection(
        _DISPLAY_SELECTION,
        string="صاحب مدرک",
        default="optional",
        required=True,
    )

    document_type_allowed_ids = fields.Many2many(
        _DOCUMENT_MODEL,
        compute="_compute_document_type_allowed_ids",
    )

    @api.model
    def _documents_folder_model(self):
        """Return the Documents model used by this module."""
        return self.env[self._DOCUMENT_MODEL]

    @api.model
    def _documents_parent_field(self):
        """Resolve the parent relation field for cross-version compatibility."""
        folder_model = self._documents_folder_model()
        for field_name in self._PARENT_CANDIDATE_FIELDS:
            if field_name in folder_model._fields:
                return field_name
        return "parent_id"

    @api.model
    def _get_document_control_roots(self):
        """Return all control root nodes named as configured by `_CONTROL_ROOT_NAME`."""
        return self._documents_folder_model().search([("name", "=", self._CONTROL_ROOT_NAME)])

    @api.model
    def _children_of(self, parents):
        """Return direct child documents for the given parent recordset."""
        if not parents:
            return self._documents_folder_model().browse()

        parent_field = self._documents_parent_field()
        return self._documents_folder_model().search([(parent_field, "in", parents.ids)])

    @api.depends("document_type_visibility")
    def _compute_document_type_allowed_ids(self):
        """Compute type candidates from children of control roots when enabled."""
        folder_model = self._documents_folder_model()
        allowed_types = self._children_of(self._get_document_control_roots())

        for rec in self:
            rec.document_type_allowed_ids = (
                allowed_types if rec.document_type_visibility != "none" else folder_model.browse()
            )
