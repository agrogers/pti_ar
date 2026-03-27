---
applyTo: '**'
---
## Framework
*   **Framework:** Odoo 18.0
*   **Key Odoo 18 feature:** Use the computed, stored `display_name` field instead of the deprecated `name_get()` method for model display names.
*   **Odoo 18 XML views:** Use `invisible="field == 'value'"` (not the legacy `attrs` dict) for conditional visibility.
*   **Odoo 18 API:** Use `@api.depends`, `@api.onchange`, `@api.constrains` decorators correctly. Avoid `@api.multi` (removed in Odoo 14+).

## Module-Specific Conventions
*   **Model technical names:** `pti.meeting.cycle`, `pti.cycle.time.slot`, `pti.partner.meeting`, `pti.meeting.member`, `pti.partner.time.slot`. Use these exactly — do not guess or abbreviate differently.
*   **Security group XML IDs:** `pti_ar.group_pti_manager`, `pti_ar.group_pti_teacher`, `pti_ar.group_pti_parent`.
*   **Time storage:** Store times of day as `Float` fields (e.g., `9.5` = 9:30 AM). Store `Datetime` fields in UTC and convert to/from the user's timezone using `pytz`.
*   **Formatting helpers:** Use `models/utils.py` (`fmt_date`, `fmt_time`) for display-name date/time formatting — do not inline equivalent formatting logic.

## General Development Instructions
*   When adding fields to models, always consider adding them to the **search view** if applicable.
*   Use `optional="hide"` in list views for secondary/rarely-used columns to give users control over visibility.
*   Always add ACL rows to `security/ir.model.access.csv` for **all three groups** (manager, teacher, parent) when creating a new model.
*   Register every new view XML file in `__manifest__.py` under `'data'`.
*   Follow Odoo naming conventions: model files snake_case, XML IDs using `pti_` prefix, relation tables named `pti_<model>_<related>_rel`.

