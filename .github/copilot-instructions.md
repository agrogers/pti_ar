# Copilot Instructions for PTI AR Module

## Overview
This is a custom Odoo 18 addon module (`pti_ar`) for managing Parent-Teacher Interview (PTI) sessions. All development must follow Odoo 18 conventions and best practices.

## Module Structure
```
pti_ar/
├── __manifest__.py         # Module metadata, dependencies, and data file list
├── __init__.py
├── models/                 # Python model definitions
│   ├── meeting_cycle.py        → pti.meeting.cycle
│   ├── meeting_cycle_time_slot.py → pti.cycle.time.slot
│   ├── partner_meeting.py      → pti.partner.meeting
│   ├── meeting_member.py       → pti.meeting.member
│   ├── partner_time_slot.py    → pti.partner.time.slot
│   ├── schedule_wizard.py      → pti.schedule.wizard (TransientModel)
│   └── utils.py                # Shared fmt_date / fmt_time helpers
├── views/                  # XML view definitions and menus
├── security/               # ACL groups and ir.model.access.csv
├── controllers/            # HTTP controllers (if needed)
├── static/                 # JS / SCSS / XML OWL components
└── tests/                  # Odoo test cases (TransactionCase)
```

## Model Technical Names (important — use these exactly)
| Python class | `_name` (technical name) | Description |
|---|---|---|
| `MeetingCycle` | `pti.meeting.cycle` | Interview period / cycle |
| `CycleTimeSlot` | `pti.cycle.time.slot` | Individual time slot in a cycle |
| `PartnerMeeting` | `pti.partner.meeting` | Actual meeting between participants |
| `MeetingMember` | `pti.meeting.member` | Participant record with role flags |
| `PartnerTimeSlot` | `pti.partner.time.slot` | A partner's booking for a time slot |

## Security Groups
| Group | XML ID | Access |
|---|---|---|
| PTI Manager | `pti_ar.group_pti_manager` | Full CRUD on all PTI models |
| PTI Teacher | `pti_ar.group_pti_teacher` | Read cycles/slots; create/edit meetings |
| PTI Parent | `pti_ar.group_pti_parent` | Read cycles/slots; manage own bookings |

Always restrict menus and views using `groups="pti_ar.group_pti_manager"` (or teacher/parent).

## Architecture & Patterns

### Display Name (Odoo 18)
Every model uses a **computed, stored** `display_name` field — never override `name_get()`:
```python
display_name = fields.Char(compute='_compute_display_name', store=True)

@api.depends('field_a', 'field_b')
def _compute_display_name(self):
    for record in self:
        record.display_name = f"{record.field_a} – {record.field_b}"
```

### Time Handling
- Times of day are stored as `Float` fields (e.g., `9.5` = 9:30 AM).
- `Datetime` fields are always stored in **UTC**; convert using `pytz`:
```python
import pytz
user_tz = pytz.timezone(self.env.user.tz or 'UTC')
utc_start = user_tz.localize(naive_local_dt).astimezone(pytz.utc).replace(tzinfo=None)
```
- Use `models/utils.py` helpers (`fmt_date`, `fmt_time`) for display formatting.

### Adding a New Model — Checklist
1. Create `models/my_model.py` with `_name`, `_description`, `_order`, fields, and `_compute_display_name`.
2. Import it in `models/__init__.py`.
3. Add ACL rows to `security/ir.model.access.csv` for all three groups.
4. Create `views/my_model_views.xml` with list, form, and search views. Use `optional="hide"` on non-essential list columns.
5. Register the view file in `__manifest__.py` under `'data'`.
6. Add a menu item in `views/menu.xml` with appropriate `groups`.
7. Update `README.md` with the new model.

### Many2many Fields
Always provide explicit relation table and column names to avoid conflicts:
```python
partner_ids = fields.Many2many(
    'res.partner',
    'pti_mymodel_partner_rel',  # unique relation table name
    'mymodel_id',
    'partner_id',
    string='Partners',
)
```

## Views

### XML Conventions
- List views: use `optional="hide"` on secondary columns.
- Form views: use `<header>` with `widget="statusbar"` for status fields.
- Search views: include all filterable fields; add `<filter>` elements for common statuses.
- Use `invisible="field == 'value'"` (not `attrs`) for Odoo 18 conditional visibility.

### Security on Views
```xml
<menuitem id="..." groups="pti_ar.group_pti_manager"/>
```

## Security CSV Format
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_pti_mymodel_manager,pti.my.model manager,model_pti_my_model,pti_ar.group_pti_manager,1,1,1,1
access_pti_mymodel_teacher,pti.my.model teacher,model_pti_my_model,pti_ar.group_pti_teacher,1,0,0,0
access_pti_mymodel_parent,pti.my.model parent,model_pti_my_model,pti_ar.group_pti_parent,1,0,0,0
```

## Testing
Place tests in `tests/` as `TransactionCase` subclasses:
```python
from odoo.tests.common import TransactionCase

class TestMeetingCycle(TransactionCase):
    def test_generate_slots(self):
        cycle = self.env['pti.meeting.cycle'].create({...})
        cycle.action_generate_time_slots()
        self.assertTrue(cycle.time_slot_ids)
```
Run a single module's tests with:
```bash
odoo-bin -d <db> --test-enable --stop-after-init -i pti_ar
```

## Developer Workflows
- **Dependencies:** Module depends on `base` only. See `__manifest__.py`.
- **Install/Upgrade:** `odoo-bin -d <db> -u pti_ar` or via **Settings → Apps**.
- **Debugging:** Use `_logger = logging.getLogger(__name__)` and Odoo's built-in debugger.
- **Documentation:** Keep `README.md` updated when adding models, fields, or workflows.
