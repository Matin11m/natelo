# Approvals Documents — Technical Documentation

## Overview
This module integrates Approvals with Documents hierarchy and follows native **Fields** policy behavior on `approval.category` with:
- `none`
- `optional`
- `required`

## Category (`approval.category`)
### Added fields
- `type_degree` (`required|optional|none`, default: `none`): selection policy controlling custom document fields on request forms.
- `document_type_allowed_ids` (computed `Many2many`): type candidates loaded from direct children of Documents roots named `کنترل مستندات`.

### Helpers
- `_documents_parent_field`: resolves parent relation (`parent_folder_id`, `parent_id`, `folder_id`).
- `_get_document_control_roots`: finds all roots named `کنترل مستندات`.
- `_children_of`: returns direct children of given roots.
- `_compute_document_type_allowed_ids`: computes type candidates when visibility is not `none`.

## Request (`approval.request`)
### Added fields
- `request_number`: unique request number generated from sequence `approvals_documents.request_number`.
- `category_type_degree`: related policy from category.
- `document_type_folder_id`: user-selectable type, domain limited to `document_type_allowed_ids`.
- `document_owner_folder_id`: user-selectable owner, domain limited to `document_owner_allowed_ids`.
- `document_type_allowed_ids` / `document_owner_allowed_ids`: computed candidate sets.

### Behavior
- If category policy is `none`, request view hides both fields and no data is selectable.
- If category policy is `optional` or `required`, request view shows both fields.
- For `required`, both fields are mandatory.
- Owner list depends on selected type.

## Views
- `approvals_category_views.xml`: injects one radio field (`type_degree`) in native `option_settings`.
- `approval_request_views.xml`: controls show/hide/required of both fields based on the single category policy.

## Sequence
- XML data file `data_sequence.xml` defines `ir.sequence` with code `approvals_documents.request_number`.
- Sequence data is loaded with `noupdate="1"` to avoid accidental counter reset during module upgrades.
- If sequence service is unavailable, a UUID-based fallback (`APRQ/FALLBACK/...`) is used to keep uniqueness guarantees.

## Validation
- `python -m compileall approvals_documents`
