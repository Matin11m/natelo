from odoo import api, fields, models


class ApprovalCategory(models.Model):
    """Extend approval categories with Documents-based type/owner classification."""

    _inherit = "approval.category"

    _DOCUMENT_MODEL = "documents.document"
    _CONTROL_ROOT_NAME = "کنترول مستندات"
    _PARENT_CANDIDATE_FIELDS = ("parent_folder_id", "parent_id", "folder_id")

    document_type_folder_id = fields.Many2one(
        _DOCUMENT_MODEL,
        string="نوع مدرک",
        domain="[('id', 'in', document_type_allowed_ids)]",
        help="Document type loaded from direct children of control root folders.",
    )
    document_owner_folder_id = fields.Many2one(
        _DOCUMENT_MODEL,
        string="صاحب مدرک",
        domain="[('id', 'in', document_owner_allowed_ids)]",
        help="Document owner loaded from direct children of selected document type.",
    )

    document_type_allowed_ids = fields.Many2many(
        _DOCUMENT_MODEL,
        compute="_compute_document_folder_domains",
    )
    document_owner_allowed_ids = fields.Many2many(
        _DOCUMENT_MODEL,
        compute="_compute_document_folder_domains",
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

    @api.depends("document_type_folder_id")
    def _compute_document_folder_domains(self):
        """Compute allowed type and owner options based on control-root hierarchy."""
        folder_model = self._documents_folder_model()
        control_roots = self._get_document_control_roots()
        allowed_type_nodes = self._children_of(control_roots)

        for rec in self:
            rec.document_type_allowed_ids = allowed_type_nodes
            rec.document_owner_allowed_ids = (
                self._children_of(rec.document_type_folder_id)
                if rec.document_type_folder_id
                else folder_model.browse()
            )

    @api.onchange("document_type_folder_id")
    def _onchange_document_type_folder_id(self):
        """Reset/filter owner options whenever document type changes."""
        self.document_owner_folder_id = False
        if not self.document_type_folder_id:
            return {"domain": {"document_owner_folder_id": [("id", "=", False)]}}

        owner_ids = self._children_of(self.document_type_folder_id).ids
        return {"domain": {"document_owner_folder_id": [("id", "in", owner_ids)]}}
