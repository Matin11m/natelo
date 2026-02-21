# Approvals Documents Override — Technical Documentation

## 1) Overview
This module extends Odoo Approvals to add a two-level document classification workflow based on Documents hierarchy:

- **Document Type** (`نوع مدرک`)
- **Document Owner** (`صاحب مدرک`)

The module applies this behavior in two places:

1. `approval.category` (configuration level)
2. `approval.request` (user request level)

The configuration source is Documents nodes named `کنترل مستندات` and their direct children.

---

## 2) Module Structure

- `__manifest__.py`
  - Declares dependencies: `approvals`, `documents`
  - Loads view overrides for category and request forms.
- `models/approvals_category.py`
  - Adds fields and domain logic for category-level configuration.
- `models/approval_request.py`
  - Adds editable request-level fields and dependent domain logic.
- `views/approvals_category_views.xml`
  - Injects category fields into approval category form.
- `views/approval_request_views.xml`
  - Injects request fields into approval request form.

---

## 3) Data Model: `approval.category`

### Added fields

1. `document_type_folder_id` (`Many2one -> documents.document`)
   - Label: `نوع مدرک`
   - Domain: limited to `document_type_allowed_ids`
   - Purpose: choose the document type from allowed control-tree nodes.

2. `document_owner_folder_id` (`Many2one -> documents.document`)
   - Label: `صاحب مدرک`
   - Domain: limited to `document_owner_allowed_ids`
   - Purpose: choose owner based on selected type.

3. `document_type_allowed_ids` (`Many2many -> documents.document`, computed)
   - Purpose: backing set used by type dropdown domain.

4. `document_owner_allowed_ids` (`Many2many -> documents.document`, computed)
   - Purpose: backing set used by owner dropdown domain.

### Class constants

- `_DOCUMENT_MODEL`
  - Target model used for documents hierarchy (`documents.document`).
- `_CONTROL_ROOT_NAME`
  - Root name searched in Documents (`کنترل مستندات`).
- `_PARENT_CANDIDATE_FIELDS`
  - Parent relation candidates for cross-version compatibility:
    - `parent_folder_id`
    - `parent_id`
    - `folder_id`

### Methods

1. `_documents_folder_model(self)`
   - Returns the model object for `_DOCUMENT_MODEL`.

2. `_documents_parent_field(self)`
   - Detects which parent relation field exists in current schema.
   - Falls back to `parent_id`.

3. `_get_document_control_roots(self)`
   - Searches all documents with name exactly `_CONTROL_ROOT_NAME`.

4. `_children_of(self, parents)`
   - Returns **direct children** of given parent recordset.
   - Returns empty recordset if no parent is provided.

5. `_compute_document_folder_domains(self)`
   - Computes allowed sets:
     - Type options = direct children of control roots.
     - Owner options = direct children of selected type.

6. `_onchange_document_type_folder_id(self)`
   - Clears owner when type changes.
   - Returns owner domain constrained to children of selected type.

---

## 4) Data Model: `approval.request`

### Added fields

1. `document_type_folder_id` (`Many2one -> documents.document`)
   - Editable in request form.
   - Domain: `document_type_allowed_ids`.

2. `document_owner_folder_id` (`Many2one -> documents.document`)
   - Editable in request form.
   - Domain: `document_owner_allowed_ids`.

3. `document_type_allowed_ids` (`Many2many`, computed)
   - Candidate set for type dropdown in request.

4. `document_owner_allowed_ids` (`Many2many`, computed)
   - Candidate set for owner dropdown in request.

### Class constants

- `_DOCUMENT_MODEL`
- `_PARENT_CANDIDATE_FIELDS`

(Used with the same purpose as category model.)

### Methods

1. `_documents_parent_field(self)`
   - Resolves parent field name for hierarchy filtering.

2. `_compute_document_allowed_ids(self)`
   - Type options come from selected category's computed allowed types.
   - Owner options depend on selected request type (direct children only).

3. `_onchange_category_id_document_defaults(self)`
   - Clears current selections when category changes.
   - Returns domains so user can pick from category-scoped type values.

4. `_onchange_document_type_folder_id(self)`
   - Clears owner on type change.
   - Filters owner list to direct children of selected type.

---

## 5) View Overrides

### `approvals_category_views.xml`

- Inherits category form view (`approvals.approval_category_view_form`).
- Adds fields:
  - `document_type_folder_id`
  - `document_owner_folder_id`
- Uses Odoo 17+ syntax (`invisible="not document_type_folder_id"`).
- Disables create/open in dropdown widgets via options:
  - `no_open`, `no_create`, `no_create_edit`, `no_quick_create`

### `approval_request_views.xml`

- Inherits request form view (`approvals.approval_request_view_form`).
- Adds same two fields after `category_id`.
- Owner field hidden until type selected.
- Same dropdown options prevent create/open from this context.

---

## 6) Functional Flow

1. Admin configures category fields in `approval.category`.
2. Type list is constrained to direct children of `کنترل مستندات` roots.
3. Owner list is constrained to direct children of selected type.
4. User creates `approval.request`.
5. After selecting category, type dropdown is scoped to category-allowed values.
6. After selecting type, owner dropdown becomes available and filtered.

---

## 7) Compatibility Notes

- Parent field detection is dynamic using `_PARENT_CANDIDATE_FIELDS`.
- This avoids hard-coding one hierarchy field name and improves portability.

---

## 8) Operational Notes / Limitations

- Root name matching is exact (`کنترل مستندات`).
- If no matching roots exist, type dropdown will be empty.
- Current behavior uses **direct children** for both levels (not recursive).

---

## 9) Maintenance Guide

Common future changes:

1. **Change root folder name**
   - Update `_CONTROL_ROOT_NAME` in `approvals_category.py`.

2. **Use recursive descendants instead of direct children**
   - Modify `_children_of` logic or introduce recursive helper.

3. **Allow create/open in dropdown**
   - Remove or adjust widget options in XML views.

4. **Make request defaults auto-selected from category**
   - Update `_onchange_category_id_document_defaults` in `approval_request.py`.

---

## 10) Quick Validation Checklist

1. Upgrade module.
2. Ensure at least one Documents node named `کنترل مستندات` exists.
3. Create children under it (type) and children under type (owner).
4. Open approval category form:
   - Type shows only allowed children.
   - Owner depends on selected type.
5. Open approval request form:
   - Category selection scopes type options.
   - Type selection scopes owner options.

