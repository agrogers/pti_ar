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

        seen = {}   # teacher.id -> index in teachers list
        for sc in student_classes:
            cls = sc.home_class_id
            class_code = getattr(cls, 'code', '') or getattr(cls, 'name', '') or ''

            # Main teachers (Many2many)
            for teacher in getattr(cls, 'teacher_ids', []):
                if teacher.id in seen:
                    # Accumulate additional class code
                    idx = seen[teacher.id]
                    existing_codes = teachers[idx]['subject'].split(', ') if teachers[idx]['subject'] else []
                    if class_code and class_code not in existing_codes:
                        existing_codes.append(class_code)
                        teachers[idx]['subject'] = ', '.join(existing_codes)
                else:
                    seen[teacher.id] = len(teachers)
                    t_image = teacher.image_128.decode('utf-8') if teacher.image_128 else False
                    tutor_code = ''
                    if self._model_exists('aps.teacher'):
                        aps_teacher = self.env['aps.teacher'].search(
                            [('partner_id', '=', teacher.id)], limit=1)
                        tutor_code = aps_teacher.tutor_code or '' if aps_teacher else ''
                    teachers.append({
                        'id': teacher.id,
                        'name': self._partner_display_name(teacher),
                        'code': tutor_code,
                        'subject': class_code,
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
            'state': slot.state or 'available',
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
        # Pre-fetch aps.student records keyed by partner_id
        aps_student_map = {}
        if self._model_exists('aps.student'):
            aps_students = self.env['aps.student'].search(
                [('partner_id', 'in', children.ids)]
            )
            aps_student_map = {s.partner_id.id: s for s in aps_students}
        students = []
        for child in children:
            image_b64 = False
            if child.image_128:
                image_b64 = child.image_128.decode('utf-8')
            aps_student = aps_student_map.get(child.id)
            year_level = aps_student.level_id.name if aps_student and aps_student.level_id else ''
            students.append({
                'id': child.id,
                'name': self._partner_display_name(child),
                'year_level': year_level,
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

        # Detect parent booking conflicts: same parent booked with 2+ teachers
        # at the same time slot (across ALL teachers, not just visible ones).
        conflict_slot_ids = []
        if parent_id:
            parent_child_ids = set(self._get_children(parent_id).ids)
            if parent_child_ids:
                # Find all booked partner_time_slots in these cycles that have
                # a meeting connected to one of the parent's children
                all_booked_pts = self.env['pti.partner.time.slot'].search([
                    ('time_slot_id', 'in', time_slots.ids),
                    ('status', '=', 'booked'),
                    ('meeting_id', '!=', False),
                ])
                # Group by slot_id: count how many distinct meetings involve
                # this parent's children
                from collections import defaultdict
                slot_meetings = defaultdict(set)
                for bpts in all_booked_pts:
                    mtg = bpts.meeting_id
                    if set(mtg.connected_partner_ids.ids) & parent_child_ids:
                        slot_meetings[bpts.time_slot_id.id].add(mtg.id)
                conflict_slot_ids = [
                    sid for sid, mids in slot_meetings.items() if len(mids) > 1
                ]

        return {
            'time_slots': [self._format_slot(s, user_tz) for s in time_slots],
            'teacher_slots': teacher_slots,
            'conflict_slot_ids': conflict_slot_ids,
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
        notes = params.get('notes', '')

        if not all([parent_id, student_id, teacher_id, slot_id]):
            raise UserError("Missing required booking parameters.")

        slot = self.env['pti.cycle.time.slot'].browse(slot_id)
        if not slot.exists():
            raise UserError("Time slot not found.")

        teacher = self.env['res.partner'].browse(teacher_id)
        if not teacher.exists():
            raise UserError("Teacher not found.")

        # Look for an existing partner-time-slot for this teacher+slot (any status)
        existing_pts = self.env['pti.partner.time.slot'].search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
        ], limit=1)

        if existing_pts and existing_pts.status == 'booked' and existing_pts.meeting_id:
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
                write_vals = {
                    'connected_partner_ids': [(6, 0, list(current_ids))],
                }
                if notes:
                    # Append note for newly added student
                    existing_notes = meeting.notes or ''
                    write_vals['notes'] = (
                        existing_notes + '\n' + notes
                    ).strip()
                meeting.write(write_vals)
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

        meeting_vals = {
            'status': 'scheduled',
            'connected_partner_ids': [(6, 0, [student_id])],
        }
        if notes:
            meeting_vals['notes'] = notes
        meeting = self.env['pti.partner.meeting'].create(meeting_vals)

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

        # Book the time slot (reuse existing record if present)
        if existing_pts:
            existing_pts.write({
                'status': 'booked',
                'meeting_id': meeting.id,
            })
        else:
            self.env['pti.partner.time.slot'].create({
                'partner_id': teacher_id,
                'time_slot_id': slot_id,
                'status': 'booked',
                'meeting_id': meeting.id,
            })

        return {'success': True, 'action': 'created', 'meeting_id': meeting.id}

    @api.model
    def cancel_meeting(self, meeting_id):
        """Cancel a meeting and release its time slots."""
        meeting = self.env['pti.partner.meeting'].browse(meeting_id)
        if not meeting.exists():
            raise UserError("Meeting not found.")
        meeting.write({'status': 'cancelled'})
        slots = self.env['pti.partner.time.slot'].search(
            [('meeting_id', '=', meeting_id)]
        )
        slots.write({'status': 'cancelled', 'meeting_id': False})
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
    def save_slot_meeting(self, params):
        """Create or update a meeting from the unified slot dialog.

        params = {
            'teacher_id': int,
            'slot_id': int,
            'meeting_id': int or False,
            'connected_student_ids': [int, ...],
            'members': [{'partner_id': int, 'is_teacher': bool,
                         'is_parent': bool, 'is_student': bool,
                         'is_observer': bool}, ...],
            'notes': str,
        }
        """
        teacher_id = params.get('teacher_id')
        slot_id = params.get('slot_id')
        meeting_id = params.get('meeting_id')
        connected_student_ids = params.get('connected_student_ids', [])
        members = params.get('members', [])
        notes = params.get('notes', '')

        if not teacher_id or not slot_id:
            raise UserError("Missing teacher or time slot.")
        if not connected_student_ids and not members:
            raise UserError("A meeting requires at least one participant.")

        slot = self.env['pti.cycle.time.slot'].browse(slot_id)
        if not slot.exists():
            raise UserError("Time slot not found.")

        MeetingMember = self.env['pti.meeting.member']
        PartnerTimeSlot = self.env['pti.partner.time.slot']

        if meeting_id:
            # --- Update existing meeting ---
            meeting = self.env['pti.partner.meeting'].browse(meeting_id)
            if not meeting.exists():
                raise UserError("Meeting not found.")

            meeting.write({
                'connected_partner_ids': [(6, 0, connected_student_ids)],
                'notes': notes,
            })

            # Replace member list: remove old, create new
            meeting.member_ids.unlink()
            member_vals = []
            for m in members:
                pid = m.get('partner_id')
                if not pid:
                    continue
                member_vals.append({
                    'meeting_id': meeting.id,
                    'partner_id': pid,
                    'is_teacher': m.get('is_teacher', False),
                    'is_parent': m.get('is_parent', False),
                    'is_student': m.get('is_student', False),
                    'is_observer': m.get('is_observer', False),
                })
            if member_vals:
                MeetingMember.create(member_vals)

            return {'success': True, 'action': 'updated', 'meeting_id': meeting.id}

        # --- Create new meeting ---
        meeting = self.env['pti.partner.meeting'].create({
            'status': 'scheduled',
            'connected_partner_ids': [(6, 0, connected_student_ids)],
            'notes': notes,
        })

        member_vals = []
        for m in members:
            pid = m.get('partner_id')
            if not pid:
                continue
            member_vals.append({
                'meeting_id': meeting.id,
                'partner_id': pid,
                'is_teacher': m.get('is_teacher', False),
                'is_parent': m.get('is_parent', False),
                'is_student': m.get('is_student', False),
                'is_observer': m.get('is_observer', False),
            })
        if member_vals:
            MeetingMember.create(member_vals)

        # Book the time slot (replace any existing unavailable record)
        existing_pts = PartnerTimeSlot.search([
            ('partner_id', '=', teacher_id),
            ('time_slot_id', '=', slot_id),
        ], limit=1)
        if existing_pts:
            existing_pts.write({
                'status': 'booked',
                'meeting_id': meeting.id,
            })
        else:
            PartnerTimeSlot.create({
                'partner_id': teacher_id,
                'time_slot_id': slot_id,
                'status': 'booked',
                'meeting_id': meeting.id,
            })

        return {'success': True, 'action': 'created', 'meeting_id': meeting.id}

    @api.model
    def get_teachers(self):
        """Return sorted list of all teachers with student counts.

        Teachers are discovered from enrolled aps.student.class records.
        """
        if not self._model_exists('aps.student.class'):
            return []

        enrolled = self.env['aps.student.class'].search([('state', '=', 'enrolled')])
        teacher_map = {}  # partner_id -> {id, name, student_count}
        for sc in enrolled:
            cls = sc.home_class_id
            for teacher in getattr(cls, 'teacher_ids', []):
                if teacher.id not in teacher_map:
                    img = teacher.image_128
                    teacher_map[teacher.id] = {
                        'id': teacher.id,
                        'name': self._partner_display_name(teacher),
                        'image': img.decode('ascii') if isinstance(img, bytes) else (img or False),
                        'student_count': 0,
                    }
                teacher_map[teacher.id]['student_count'] += 1

        return sorted(teacher_map.values(), key=lambda x: x['name'])

    @api.model
    def get_teacher_data(self, teacher_id):
        """Return students and their class codes for the given teacher.

        Each student entry includes:
        - id (partner_id)
        - name
        - image
        - classes: list of {class_id, class_code}
        - parent_id: best parent (favour mother)
        """
        if not teacher_id or not self._model_exists('aps.student.class'):
            return {'students': [], 'teacher_id': teacher_id}

        teacher = self.env['res.partner'].browse(teacher_id)
        if not teacher.exists():
            return {'students': [], 'teacher_id': teacher_id}

        # Find all classes this teacher teaches
        classes = self.env['aps.class'].search([
            ('teacher_ids', 'in', [teacher_id]),
        ])

        # Get enrolled students in those classes
        enrollments = self.env['aps.student.class'].search([
            ('home_class_id', 'in', classes.ids),
            ('state', '=', 'enrolled'),
        ])

        student_map = {}  # partner_id -> {id, name, image, classes, parent_id}
        for sc in enrollments:
            student = sc.student_id
            partner = student.partner_id
            if not partner:
                continue
            pid = partner.id
            cls = sc.home_class_id
            class_code = getattr(cls, 'code', '') or getattr(cls, 'name', '') or ''

            if pid not in student_map:
                image_b64 = partner.image_128.decode('utf-8') if partner.image_128 else False
                parent = self._get_parent_for_student(pid)
                student_map[pid] = {
                    'id': pid,
                    'name': self._partner_display_name(partner),
                    'image': image_b64,
                    'classes': [],
                    'parent_id': parent['id'] if parent else False,
                    'parent_name': parent['name'] if parent else '',
                }
            if class_code and class_code not in [c['class_code'] for c in student_map[pid]['classes']]:
                student_map[pid]['classes'].append({
                    'class_id': cls.id,
                    'class_code': class_code,
                })

        students = sorted(student_map.values(), key=lambda x: x['name'])
        return {'students': students, 'teacher_id': teacher_id}

    def _get_parent_for_student(self, student_partner_id):
        """Return {'id', 'name'} for the best parent of a student.

        Prefers mother (is Parent of) over guardian (Is Guardian Of).
        """
        if not self._model_exists('res.partner.relation.all'):
            return False

        # Search for parent relations where the student is the child
        # In the relation model the *parent* is this_partner, child is other_partner
        # (type "is Parent of" means this_partner IS PARENT OF other_partner)
        # So we search where other_partner is the student (is_inverse=True perspective)
        relations = self.env['res.partner.relation.all'].search([
            ('other_partner_id', '=', student_partner_id),
            ('type_id.name', 'in', ['is Parent of', 'Is Guardian Of']),
            ('is_inverse', '=', False),
        ])

        if not relations:
            return False

        # Favour mother — check if partner has title "Mrs" or "Ms" or gender
        best = None
        for rel in relations:
            p = rel.this_partner_id
            if best is None:
                best = p
            else:
                # Prefer female / mother
                p_title = (p.title.name or '').lower() if p.title else ''
                if 'mrs' in p_title or 'ms' in p_title or 'mother' in p_title:
                    best = p
                    break
        return {'id': best.id, 'name': self._partner_display_name(best)}

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
