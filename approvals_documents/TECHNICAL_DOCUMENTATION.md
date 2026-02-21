# Approvals Documents — Technical Documentation

## Overview
This module integrates Approvals with Documents hierarchy and follows the native **Fields** behavior in `approval.category` (None / Optional / Required).

## Category (`approval.category`)
### Added fields
- `document_type_visibility` (`none|optional|required`): controls display/requirement policy for document type in requests.
- `document_owner_visibility` (`none|optional|required`): controls display/requirement policy for document owner in requests.
- `document_type_allowed_ids` (computed `Many2many`): available type candidates loaded from direct children of Documents roots named `کنترل مستندات`.

### Helpers
- `_documents_parent_field`: resolves parent relation (`parent_folder_id`, `parent_id`, `folder_id`).
- `_get_document_control_roots`: finds all roots named `کنترل مستندات`.
- `_children_of`: returns direct children of given roots.
- `_compute_document_type_allowed_ids`: computes category-scoped type candidates when visibility is not `none`.

## Request (`approval.request`)
### Added fields
- `document_type_folder_id`: user-selectable type, domain limited to `document_type_allowed_ids`.
- `document_owner_folder_id`: user-selectable owner, domain limited to `document_owner_allowed_ids`.
- `document_type_allowed_ids` / `document_owner_allowed_ids`: computed candidate sets.
- `category_document_type_visibility` / `category_document_owner_visibility`: related visibility flags from category.

### Behavior
- If category visibility is `none`, corresponding request field is hidden and receives no selectable data.
- If `optional` or `required`, request field is shown; for `required` it becomes mandatory.
- Owner list is always dependent on selected type.

## Views
- `approvals_category_views.xml`: injects the two visibility fields inside native `Fields` group (`option_settings`) as horizontal radio widgets.
- `approval_request_views.xml`: shows/hides and requires request fields based on category visibility selections.

## Validation
- `python -m compileall approvals_documents`
