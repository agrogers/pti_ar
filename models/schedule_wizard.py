import pytz

from odoo import api, models
from odoo.exceptions import UserError


class PtiScheduleMeetings(models.AbstractModel):
    _name = 'pti.schedule.meetings'
    _description = 'PTI Schedule Meetings Helper'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _model_exists(self, model_name):
        return model_name in self.env

    def _get_children(self, parent_id):
        """Return res.partner recordset of children for the given parent."""
        if not self._model_exists('res.partner.relation.all'):
            return self.env['res.partner']
        relations = self.env['res.partner.relation.all'].search([
            ('this_partner_id', '=', parent_id),
            ('type_id.name', 'in', ['Is Parent Of', 'Is Guardian Of']),
        ])
        return relations.mapped('other_partner_id')

    def _get_spouse(self, parent_id):
        """Return {'id', 'name'} for the spouse, or False."""
        if not self._model_exists('res.partner.relation.all'):
            return False
        relations = self.env['res.partner.relation.all'].search([
            ('this_partner_id', '=', parent_id),
            ('type_id.name', 'in', ['Is Married To', 'Is Spouse Of', 'Spouse']),
        ], limit=1)
        if relations:
            s = relations[0].other_partner_id
            return {'id': s.id, 'name': s.name or ''}
        return False

    def _get_student_teachers(self, student_id):
        """Return list of teacher dicts for an enrolled student."""
        teachers = []
        if not self._model_exists('aps.student.class'):
            return teachers

        student_classes = self.env['aps.student.class'].search([
            ('student_id', '=', student_id),
            ('status', '=', 'enrolled'),
        ])

        seen = set()
        for sc in student_classes:
            cls = sc.class_id
            subject = getattr(cls, 'name', '') or ''

            # Main teacher
            teacher = getattr(cls, 'teacher_id', False)
            if teacher and teacher.id not in seen:
                seen.add(teacher.id)
                teachers.append({
                    'id': teacher.id,
                    'name': teacher.name or '',
                    'subject': subject,
                    'is_assistant': False,
                    'class_id': cls.id,
                })

            # Assistant teachers (observers)
            for asst in getattr(cls, 'assistant_teacher_ids', []):
                if asst.id not in seen:
                    seen.add(asst.id)
                    teachers.append({
                        'id': asst.id,
                        'name': asst.name or '',
                        'subject': subject,
                        'is_assistant': True,
                        'class_id': cls.id,
                    })

        return teachers

    def _get_assistant_ids_for_teacher_student(self, teacher_id, student_ids):
        """Return set of assistant partner IDs for the teacher/student class combo."""
        if not self._model_exists('aps.student.class'):
            return set()
        assistant_ids = set()
        for student_id in student_ids:
            scs = self.env['aps.student.class'].search([
                ('student_id', '=', student_id),
                ('status', '=', 'enrolled'),
            ])
            for sc in scs:
                cls = sc.class_id
                if getattr(cls, 'teacher_id', False) and cls.teacher_id.id == teacher_id:
                    for asst in getattr(cls, 'assistant_teacher_ids', []):
                        assistant_ids.add(asst.id)
        return assistant_ids

    def _format_slot(self, slot, user_tz):
        start_local = pytz.utc.localize(slot.start_date_time).astimezone(user_tz)
        end_local = pytz.utc.localize(slot.end_date_time).astimezone(user_tz)

        def _fmt_time(dt):
            # Use %-I on Linux/Mac to suppress the leading zero on the hour.
            try:
                return dt.strftime('%-I:%M %p')
            except ValueError:
                # Windows fallback
                return dt.strftime('%I:%M %p').lstrip('0') or '0'

        return {
            'id': slot.id,
            'start': slot.start_date_time.isoformat(),
            'end': slot.end_date_time.isoformat(),
            'start_display': _fmt_time(start_local),
            'end_display': _fmt_time(end_local),
            'date_display': start_local.strftime('%a %b %d'),
        }

    # ------------------------------------------------------------------
    # Public API called from the OWL component
    # ------------------------------------------------------------------

    @api.model
    def get_parents(self):
        """Return sorted list of parent partners with child counts."""
        parents = []
        if not self._model_exists('res.partner.relation.all'):
            return parents

        relations = self.env['res.partner.relation.all'].search([
            ('type_id.name', 'in', ['Is Parent Of', 'Is Guardian Of']),
        ])

        # Group by parent partner
        parent_map = {}
        for rel in relations:
            p = rel.this_partner_id
            if p.id not in parent_map:
                parent_map[p.id] = {'id': p.id, 'name': p.name or '', 'child_count': 0}
            parent_map[p.id]['child_count'] += 1

        return sorted(parent_map.values(), key=lambda x: x['name'])

    @api.model
    def get_parent_data(self, parent_id):
        """Return students and their teachers for the given parent."""
        if not parent_id:
            return {'students': [], 'spouse': False}

        children = self._get_children(parent_id)
        students = []
        for child in children:
            image_b64 = False
            if child.image_128:
                image_b64 = child.image_128.decode('utf-8')
            students.append({
                'id': child.id,
                'name': child.name or '',
                'image': image_b64,
                'teachers': self._get_student_teachers(child.id),
            })

        return {
            'students': students,
            'spouse': self._get_spouse(parent_id),
        }

    @api.model
    def get_slot_data(self, teacher_ids, parent_id):
        """Return time slots and per-teacher booking status."""
        if not teacher_ids:
            return {'time_slots': [], 'teacher_slots': {}}

        # Active cycle(s), fall back to most recent
        active_cycles = self.env['pti.meeting.cycle'].search([('status', '=', 'active')])
        if not active_cycles:
            active_cycles = self.env['pti.meeting.cycle'].search([], order='start_date desc', limit=1)
        if not active_cycles:
            return {'time_slots': [], 'teacher_slots': {}}

        time_slots = self.env['pti.cycle.time.slot'].search(
            [('meeting_cycle_id', 'in', active_cycles.ids)],
            order='start_date_time',
        )

        # Partner-time-slot records for these teachers
        partner_slots = self.env['pti.partner.time.slot'].search([
            ('time_slot_id', 'in', time_slots.ids),
            ('partner_id', 'in', teacher_ids),
            ('status', 'not in', ['cancelled']),
        ])

        # Pre-fetch meeting data
        meeting_ids = partner_slots.mapped('meeting_id').filtered(lambda m: m).ids
        meeting_data_map = {}
        if meeting_ids:
            parent_child_ids = set(self._get_children(parent_id).ids) if parent_id else set()
            for meeting in self.env['pti.partner.meeting'].browse(meeting_ids):
                connected = meeting.connected_partner_ids.ids
                teachers_cnt = sum(1 for m in meeting.member_ids if m.is_teacher)
                observers_cnt = sum(1 for m in meeting.member_ids if m.is_observer)
                parents_students_cnt = sum(1 for m in meeting.member_ids if m.is_parent or m.is_student)
                is_parent_meeting = bool(set(connected) & parent_child_ids)
                meeting_data_map[meeting.id] = {
                    'id': meeting.id,
                    'status': meeting.status,
                    'connected_partner_ids': connected,
                    'is_parent_meeting': is_parent_meeting,
                    'teachers_count': teachers_cnt,
                    'observers_count': observers_cnt,
                    'parents_students_count': parents_students_cnt,
                    'notes': meeting.notes or '',
                    'members': [
                        {
                            'partner_id': m.partner_id.id,
                            'partner_name': m.partner_id.name or '',
                            'is_teacher': m.is_teacher,
                            'is_parent': m.is_parent,
                            'is_student': m.is_student,
                            'is_observer': m.is_observer,
                        }
                        for m in meeting.member_ids
                    ],
                }

        # Build teacher_slots: {str(teacher_id): {str(slot_id): {...}}}
        teacher_slots = {str(tid): {} for tid in teacher_ids}
        for ps in partner_slots:
            t_key = str(ps.partner_id.id)
            s_key = str(ps.time_slot_id.id)
            mtg = meeting_data_map.get(ps.meeting_id.id) if ps.meeting_id else None
            teacher_slots.setdefault(t_key, {})[s_key] = {
                'partner_slot_id': ps.id,
                'status': ps.status,
                'meeting_id': ps.meeting_id.id if ps.meeting_id else False,
                'meeting': mtg,
            }

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        return {
            'time_slots': [self._format_slot(s, user_tz) for s in time_slots],
            'teacher_slots': teacher_slots,
        }

    @api.model
    def book_meeting(self, params):
        """Create a meeting and a booked partner-time-slot for the teacher."""
        parent_id = params.get('parent_id')
        student_ids = params.get('student_ids') or []
        teacher_id = params.get('teacher_id')
        slot_id = params.get('slot_id')
        include_students = params.get('include_students', False)
        include_spouse = params.get('include_spouse', False)

        if not all([parent_id, teacher_id, slot_id]):
            raise UserError("Missing required booking parameters.")

        slot = self.env['pti.cycle.time.slot'].browse(slot_id)
        if not slot.exists():
            raise UserError("Time slot not found.")

        teacher = self.env['res.partner'].browse(teacher_id)
        if not teacher.exists():
            raise UserError("Teacher not found.")

        # Check not already booked for this teacher+slot
        existing = self.env['pti.partner.time.slot'].search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
            ('status', '=', 'booked'),
        ], limit=1)
        if existing:
            raise UserError(f"This time slot is already booked for {teacher.name}.")

        # Get assistant teachers for these students + teacher
        assistant_ids = self._get_assistant_ids_for_teacher_student(teacher_id, student_ids)

        # Create the meeting
        meeting = self.env['pti.partner.meeting'].create({
            'status': 'scheduled',
            'connected_partner_ids': [(6, 0, student_ids)],
        })

        member_vals = [
            # Main teacher
            {'meeting_id': meeting.id, 'partner_id': teacher_id, 'is_teacher': True},
        ]

        # Observers (assistant teachers)
        for aid in assistant_ids:
            member_vals.append(
                {'meeting_id': meeting.id, 'partner_id': aid, 'is_observer': True}
            )

        # Parent (always added)
        member_vals.append(
            {'meeting_id': meeting.id, 'partner_id': parent_id, 'is_parent': True}
        )

        # Spouse
        if include_spouse:
            spouse = self._get_spouse(parent_id)
            if spouse:
                member_vals.append(
                    {'meeting_id': meeting.id, 'partner_id': spouse['id'], 'is_parent': True}
                )

        # Students
        if include_students:
            for sid in student_ids:
                member_vals.append(
                    {'meeting_id': meeting.id, 'partner_id': sid, 'is_student': True}
                )

        self.env['pti.meeting.member'].create(member_vals)

        # Create the teacher's booked time slot
        self.env['pti.partner.time.slot'].create({
            'partner_id': teacher_id,
            'time_slot_id': slot_id,
            'status': 'booked',
            'meeting_id': meeting.id,
        })

        return {'success': True, 'meeting_id': meeting.id}

    @api.model
    def cancel_meeting(self, meeting_id):
        """Cancel a meeting and mark its time slots as cancelled."""
        meeting = self.env['pti.partner.meeting'].browse(meeting_id)
        if not meeting.exists():
            raise UserError("Meeting not found.")
        meeting.write({'status': 'cancelled'})
        self.env['pti.partner.time.slot'].search(
            [('meeting_id', '=', meeting_id)]
        ).write({'status': 'cancelled'})
        return {'success': True}

    @api.model
    def save_meeting_notes(self, meeting_id, notes):
        """Persist notes on a meeting."""
        meeting = self.env['pti.partner.meeting'].browse(meeting_id)
        if not meeting.exists():
            raise UserError("Meeting not found.")
        meeting.write({'notes': notes})
        return {'success': True}
