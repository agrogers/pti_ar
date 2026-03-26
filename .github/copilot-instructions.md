# Copilot Instructions for PTI AR Module

## Overview
This is a custom Odoo 18 addon module (`pti_ar`). All development must follow Odoo 18 conventions and best practices.

## Architecture & Patterns
- **Odoo 18 Core:** All development follows Odoo 18 conventions. Use `display_name` for model display names (not the deprecated `name_get()`).
- **Module Structure:** Standard Odoo addon layout: `models/`, `views/`, `security/`, `controllers/`, `wizard/`, `static/`, `tests/`.
- **Views:** XML views use Odoo 18 syntax. Add new fields to search views and use the `optional` attribute for user customization.
- **Security:** Follow Odoo 18 ACL and record rule patterns. Security files are in `security/`.
- **Testing:** Use Odoo 18's testing framework. Place tests in the `tests/` directory.

## Developer Workflows
- **Dependencies:** This module depends on Odoo 18 (`base` module at minimum). See `__manifest__.py` for full dependency list.
- **Module Installation:** Install via Odoo UI or CLI. Ensure `__manifest__.py` is correct.
- **Debugging:** Use Odoo logging and Python debuggers.

## Project-Specific Conventions
- **Naming:** Follow Odoo naming conventions for models, fields, and files.
- **Documentation:** Keep `README.md` updated with integration and usage instructions.

## Key Files
- `__manifest__.py`: Module metadata, dependencies, and data files.
- `models/`: Python model definitions.
- `views/`: XML view definitions and menus.
- `security/`: Access control lists and record rules.

## Code Examples
- **View XML:** Use `<field optional="hide">` for user-customizable optional fields.
- **Model Display Name (Odoo 18):**
  ```python
  display_name = fields.Char(compute="_compute_display_name")
  ```
- **Security CSV:**
  ```csv
  id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
  ```
