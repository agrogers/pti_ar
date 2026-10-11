from odoo import fields, http
from odoo.http import request


class PtiParentPortal(http.Controller):
    @staticmethod
    def _clear_code_session():
        request.session.pop('pti_parent_partner_id', None)
        request.session.pop('pti_parent_access_code', None)

    def _parent_partner(self):
        if request.env.user.has_group('base.group_portal'):
            return request.env.user.partner_id.sudo()

        partner_id = request.session.get('pti_parent_partner_id')
        access_code = request.session.get('pti_parent_access_code')
        if not partner_id or not access_code:
            return request.env['res.partner']

        parent = request.env['res.partner'].sudo().browse(partner_id).exists()
        if not parent or parent.pti_portal_access_code != access_code:
            self._clear_code_session()
            return request.env['res.partner']
        return parent

    @staticmethod
    def _positive_id(value):
        value = str(value or '')
        return int(value) if value.isdecimal() and int(value) > 0 else False

    def _render_portal(self, parent=None, error=None):
        values = {
            'parent': parent,
            'error': error,
            'teachers': [],
            'cycle_names': [],
            'has_active_cycle': False,
        }
        if not parent:
            return request.render('pti_ar.portal_parent_interviews', values)

        Schedule = request.env['pti.schedule.meetings'].sudo()
        parent_data = Schedule.get_parent_data(parent.id)
        child_ids = {student['id'] for student in parent_data['students']}
        teachers_by_id = {}
        for student in parent_data['students']:
            for teacher in student['teachers']:
                teacher_data = teachers_by_id.setdefault(teacher['id'], {
                    'id': teacher['id'],
                    'name': teacher['name'],
                    'students': [],
                })
                teacher_data['students'].append({
                    'id': student['id'],
                    'name': student['name'],
                    'available_slots': [],
                    'booked_slots': [],
                })

        teachers = sorted(teachers_by_id.values(), key=lambda teacher: teacher['name'])
        teacher_ids = [teacher['id'] for teacher in teachers]
        cycles = request.env['pti.meeting.cycle'].sudo().search([
            ('status', '=', 'active'),
        ])
        values.update({
            'teachers': teachers,
            'cycle_names': cycles.mapped('name'),
            'has_active_cycle': bool(cycles),
        })

        if cycles and teacher_ids:
            slot_data = Schedule.get_slot_data(teacher_ids, parent.id)
            future_slot_ids = set(request.env['pti.cycle.time.slot'].sudo().search([
                ('meeting_cycle_id', 'in', cycles.ids),
                ('start_date_time', '>', fields.Datetime.now()),
            ]).ids)
            for teacher in teachers:
                teacher_slots = slot_data['teacher_slots'].get(str(teacher['id']), {})
                for student in teacher['students']:
                    for slot in slot_data['time_slots']:
                        if slot['state'] != 'available':
                            continue

                        slot_info = teacher_slots.get(str(slot['id']))
                        if slot_info and slot_info['status'] == 'unavailable':
                            continue

                        meeting = slot_info.get('meeting') if slot_info else False
                        if slot_info and slot_info['status'] == 'booked':
                            if not meeting or meeting['status'] not in ('scheduled', 'confirmed'):
                                continue
                            meeting_student_ids = set(meeting['connected_partner_ids'])
                            family_booking = bool(meeting_student_ids & child_ids)
                            if not family_booking:
                                continue
                            if student['id'] in meeting_student_ids:
                                booking = dict(slot)
                                booking['can_cancel'] = slot['id'] in future_slot_ids
                                student['booked_slots'].append(booking)
                                continue

                        if slot_info and slot_info['status'] not in ('available', 'cancelled', 'booked'):
                            continue
                        if slot['id'] not in future_slot_ids:
                            continue
                        student['available_slots'].append(slot)

        return request.render('pti_ar.portal_parent_interviews', values)

    @http.route(
        '/my/pti',
        type='http',
        auth='public',
        website=True,
        methods=['GET', 'POST'],
    )
    def portal_parent_interviews(self, **post):
        if request.httprequest.method == 'POST':
            if 'access_code' in post:
                code = (post.get('access_code') or '').strip().upper()
                parent = request.env['res.partner'].sudo().search([
                    ('pti_portal_access_code', '=', code),
                ], limit=1) if code else request.env['res.partner']
                if not parent or not request.env['pti.schedule.meetings'].sudo()._get_children(parent.id):
                    return self._render_portal(error='That login code is not valid.')

                request.session['pti_parent_partner_id'] = parent.id
                request.session['pti_parent_access_code'] = code
                return request.redirect('/my/pti')

            parent = self._parent_partner()
            if not parent:
                return request.redirect('/my/pti')

            action = post.get('action')
            student_id = self._positive_id(post.get('student_id'))
            teacher_id = self._positive_id(post.get('teacher_id'))
            slot_id = self._positive_id(post.get('slot_id'))
            if action not in ('book', 'cancel') or not all((student_id, teacher_id, slot_id)):
                return self._render_portal(parent, 'Please choose a valid student and time.')

            Schedule = request.env['pti.schedule.meetings'].sudo()
            parent_data = Schedule.get_parent_data(parent.id)
            student = next(
                (item for item in parent_data['students'] if item['id'] == student_id),
                None,
            )
            if not student:
                return self._render_portal(parent, 'That student is not linked to your account.')
            if teacher_id not in {teacher['id'] for teacher in student['teachers']}:
                return self._render_portal(parent, 'That teacher is not assigned to this student.')

            Slot = request.env['pti.cycle.time.slot'].sudo()
            slot = Slot.browse(slot_id).exists()
            if not slot or slot.meeting_cycle_id.status != 'active' or slot.state != 'available':
                return self._render_portal(parent, 'That time is no longer available.')
            if slot.start_date_time <= fields.Datetime.now():
                return self._render_portal(parent, 'That time is no longer available.')

            PartnerTimeSlot = request.env['pti.partner.time.slot'].sudo()
            partner_slot = PartnerTimeSlot.search([
                ('partner_id', '=', teacher_id),
                ('time_slot_id', '=', slot_id),
            ], limit=1)
            if action == 'cancel':
                meeting = partner_slot.meeting_id if partner_slot else False
                if (
                    not partner_slot
                    or partner_slot.status != 'booked'
                    or not meeting
                    or meeting.status not in ('scheduled', 'confirmed')
                    or student_id not in meeting.connected_partner_ids.ids
                ):
                    return self._render_portal(parent, 'That booking can no longer be cancelled.')
            elif partner_slot and partner_slot.status == 'unavailable':
                return self._render_portal(parent, 'That time is no longer available.')
            elif partner_slot and partner_slot.status == 'booked':
                meeting = partner_slot.meeting_id
                child_ids = {item['id'] for item in parent_data['students']}
                if (
                    not meeting
                    or meeting.status not in ('scheduled', 'confirmed')
                    or not (set(meeting.connected_partner_ids.ids) & child_ids)
                ):
                    return self._render_portal(parent, 'That time is no longer available.')
                if student_id in meeting.connected_partner_ids.ids:
                    return request.redirect('/my/pti')
            elif partner_slot and partner_slot.status not in ('available', 'cancelled'):
                return self._render_portal(parent, 'That time is no longer available.')

            Schedule.toggle_student_on_meeting({
                'parent_id': parent.id,
                'student_id': student_id,
                'teacher_id': teacher_id,
                'slot_id': slot_id,
                'include_students': False,
                'include_spouse': False,
            })
            return request.redirect('/my/pti')

        parent = self._parent_partner()
        return self._render_portal(parent)

    @http.route(
        '/my/pti/logout',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def portal_parent_interviews_logout(self):
        self._clear_code_session()
        return request.redirect('/my/pti')
