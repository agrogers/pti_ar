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

    @staticmethod
    def _partner_display_name(partner):
        """Return customer_name if set, otherwise name."""
        return partner.customer_name or partner.name or ''

    def _get_children(self, parent_id):
        """Return res.partner recordset of children for the given parent."""
        if not self._model_exists('res.partner.relation.all'):
            return self.env['res.partner']
        relations = self.env['res.partner.relation.all'].search([
            ('this_partner_id', '=', parent_id),
            ('type_id.name', 'in', ['is Parent of', 'Is Guardian Of']),
        ])
        return relations.mapped('other_partner_id')

    def _get_spouse(self, parent_id):
        """Return {'id', 'name'} for the spouse, or False."""
        if not self._model_exists('res.partner.relation.all'):
            return False
        relations = self.env['res.partner.relation.all'].search([
            ('this_partner_id', '=', parent_id),
            ('type_id.name', 'in', ['is Married to', 'is Spouse of', 'Spouse']),
        ], limit=1)
        if relations:
            s = relations[0].other_partner_id
            return {'id': s.id, 'name': self._partner_display_name(s)}
        return False

    def _get_student_teachers(self, partner_id):
        """Return list of teacher dicts for an enrolled student (by partner ID)."""
        teachers = []
        if not self._model_exists('aps.student.class'):
            return teachers

        student_classes = self.env['aps.student.class'].search([
            ('student_id.partner_id', '=', partner_id),
            ('state', '=', 'enrolled'),
        ])

        seen = set()
        for sc in student_classes:
            cls = sc.home_class_id
            subject = getattr(cls, 'name', '') or ''

            # Main teachers (Many2many)
            for teacher in getattr(cls, 'teacher_ids', []):
                if teacher.id not in seen:
                    seen.add(teacher.id)
                    t_image = teacher.image_128.decode('utf-8') if teacher.image_128 else False
                    teachers.append({
                        'id': teacher.id,
                        'name': self._partner_display_name(teacher),
                        'subject': subject,
                        'is_assistant': False,
                        'class_id': cls.id,
                        'image': t_image,
                    })

            # # Assistant teachers
            # for asst in getattr(cls, 'assistant_teacher_ids', []):
            #     if asst.id not in seen:
            #         seen.add(asst.id)
            #         teachers.append({
            #             'id': asst.id,
            #             'name': asst.name or '',
            #             'subject': subject,
            #             'is_assistant': True,
            #             'class_id': cls.id,
            #         })

        return teachers

    def _get_assistant_ids_for_teacher_student(self, teacher_id, student_ids):
        """Return set of assistant partner IDs for the teacher/student class combo.
        
        teacher_id and student_ids are res.partner IDs.
        """
        if not self._model_exists('aps.student.class'):
            return set()
        assistant_ids = set()
        for sid in student_ids:
            scs = self.env['aps.student.class'].search([
                ('student_id.partner_id', '=', sid),
                ('state', '=', 'enrolled'),
            ])
            for sc in scs:
                cls = sc.home_class_id
                if teacher_id in getattr(cls, 'teacher_ids', self.env['res.partner']).ids:
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
            ('type_id.name', 'in', ['is Parent of', 'is Guardian of']),
            ('is_inverse', '=', False),
        ])

        # Group by parent partner (this_partner_id = left = parent)
        parent_map = {}
        for rel in relations:
            p = rel.this_partner_id
            if p.id not in parent_map:
                parent_map[p.id] = {'id': p.id, 'name': self._partner_display_name(p), 'child_count': 0}
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
                'name': self._partner_display_name(child),
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
                connected = meeting.connected_partner_ids
                connected_ids = connected.ids
                connected_names = [self._partner_display_name(p) for p in connected]
                connected_partners = []
                for cp in connected:
                    cp_image = cp.image_128.decode('utf-8') if cp.image_128 else False
                    connected_partners.append({
                        'id': cp.id,
                        'name': self._partner_display_name(cp),
                        'image': cp_image,
                    })
                teachers_cnt = sum(1 for m in meeting.member_ids if m.is_teacher)
                observers_cnt = sum(1 for m in meeting.member_ids if m.is_observer)
                parents_students_cnt = sum(1 for m in meeting.member_ids if m.is_parent or m.is_student)
                is_parent_meeting = bool(set(connected_ids) & parent_child_ids)
                meeting_data_map[meeting.id] = {
                    'id': meeting.id,
                    'status': meeting.status,
                    'connected_partner_ids': connected_ids,
                    'connected_partner_names': connected_names,
                    'connected_partners': connected_partners,
                    'is_parent_meeting': is_parent_meeting,
                    'teachers_count': teachers_cnt,
                    'observers_count': observers_cnt,
                    'parents_students_count': parents_students_cnt,
                    'notes': meeting.notes or '',
                    'members': [
                        {
                            'partner_id': m.partner_id.id,
                            'partner_name': self._partner_display_name(m.partner_id),
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
    def toggle_student_on_meeting(self, params):
        """Toggle a student on/off a meeting for a teacher+slot.

        If no meeting exists yet, create one (book the slot).
        If the student is already connected, remove them.
        If removed and no students remain, cancel the meeting.
        """
        parent_id = params.get('parent_id')
        student_id = params.get('student_id')
        teacher_id = params.get('teacher_id')
        slot_id = params.get('slot_id')
        include_students = params.get('include_students', False)
        include_spouse = params.get('include_spouse', False)

        if not all([parent_id, student_id, teacher_id, slot_id]):
            raise UserError("Missing required booking parameters.")

        slot = self.env['pti.cycle.time.slot'].browse(slot_id)
        if not slot.exists():
            raise UserError("Time slot not found.")

        teacher = self.env['res.partner'].browse(teacher_id)
        if not teacher.exists():
            raise UserError("Teacher not found.")

        # Look for an existing booked partner-time-slot for this teacher+slot
        existing_pts = self.env['pti.partner.time.slot'].search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
            ('status', '=', 'booked'),
        ], limit=1)

        if existing_pts and existing_pts.meeting_id:
            meeting = existing_pts.meeting_id
            current_ids = set(meeting.connected_partner_ids.ids)

            if student_id in current_ids:
                # Remove student
                current_ids.discard(student_id)
                if not current_ids:
                    # Last student removed — cancel the meeting
                    meeting.write({'status': 'cancelled'})
                    existing_pts.write({'status': 'cancelled'})
                    return {'success': True, 'action': 'cancelled'}
                else:
                    meeting.write({
                        'connected_partner_ids': [(6, 0, list(current_ids))],
                    })
                    # Remove student member record if present
                    meeting.member_ids.filtered(
                        lambda m: m.partner_id.id == student_id and m.is_student
                    ).unlink()
                    return {'success': True, 'action': 'removed'}
            else:
                # Add student
                current_ids.add(student_id)
                meeting.write({
                    'connected_partner_ids': [(6, 0, list(current_ids))],
                })
                if include_students:
                    # Add student member record if not already there
                    if not meeting.member_ids.filtered(
                        lambda m: m.partner_id.id == student_id and m.is_student
                    ):
                        self.env['pti.meeting.member'].create({
                            'meeting_id': meeting.id,
                            'partner_id': student_id,
                            'is_student': True,
                        })
                return {'success': True, 'action': 'added'}

        # No existing meeting — create one
        assistant_ids = self._get_assistant_ids_for_teacher_student(
            teacher_id, [student_id]
        )

        meeting = self.env['pti.partner.meeting'].create({
            'status': 'scheduled',
            'connected_partner_ids': [(6, 0, [student_id])],
        })

        member_vals = [
            {'meeting_id': meeting.id, 'partner_id': teacher_id, 'is_teacher': True},
        ]
        for aid in assistant_ids:
            member_vals.append(
                {'meeting_id': meeting.id, 'partner_id': aid, 'is_observer': True}
            )
        member_vals.append(
            {'meeting_id': meeting.id, 'partner_id': parent_id, 'is_parent': True}
        )
        if include_spouse:
            spouse = self._get_spouse(parent_id)
            if spouse:
                member_vals.append(
                    {'meeting_id': meeting.id, 'partner_id': spouse['id'], 'is_parent': True}
                )
        if include_students:
            member_vals.append(
                {'meeting_id': meeting.id, 'partner_id': student_id, 'is_student': True}
            )

        self.env['pti.meeting.member'].create(member_vals)

        self.env['pti.partner.time.slot'].create({
            'partner_id': teacher_id,
            'time_slot_id': slot_id,
            'status': 'booked',
            'meeting_id': meeting.id,
        })

        return {'success': True, 'action': 'created', 'meeting_id': meeting.id}

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

    @api.model
    def set_slot_unavailable(self, teacher_id, slot_id):
        """Mark a teacher's time slot as unavailable.

        If a booked meeting exists, it is cancelled first.
        Returns {'success': True, 'cancelled_meeting': <bool>}.
        """
        slot = self.env['pti.cycle.time.slot'].browse(slot_id)
        if not slot.exists():
            raise UserError("Time slot not found.")

        # Find or create the partner-time-slot record
        pts = self.env['pti.partner.time.slot'].search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
        ], limit=1)

        cancelled_meeting = False
        if pts and pts.meeting_id:
            meeting = pts.meeting_id
            meeting.write({'status': 'cancelled'})
            # Free all partner-time-slots linked to this meeting
            self.env['pti.partner.time.slot'].search(
                [('meeting_id', '=', meeting.id)]
            ).write({'status': 'cancelled', 'meeting_id': False})
            cancelled_meeting = True

        if pts:
            pts.write({'status': 'unavailable', 'meeting_id': False})
        else:
            self.env['pti.partner.time.slot'].create({
                'partner_id': teacher_id,
                'time_slot_id': slot_id,
                'status': 'unavailable',
            })

        return {'success': True, 'cancelled_meeting': cancelled_meeting}

    @api.model
    def set_slot_available(self, teacher_id, slot_id):
        """Mark a teacher's time slot back to available."""
        pts = self.env['pti.partner.time.slot'].search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
            ('status', '=', 'unavailable'),
        ], limit=1)
        if pts:
            pts.write({'status': 'available'})
        return {'success': True}
