from datetime import datetime

import pytz

from odoo import api, models

from ..models import utils


class ParentScheduleReport(models.AbstractModel):
    _name = 'report.pti_ar.parent_schedule_report'
    _description = 'Parent Schedule Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        summaries = self.env['pti.parent.meeting.summary'].browse(docids)
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        report_data = []

        for summary in summaries:
            parent = summary.parent_id
            cycle = summary.meeting_cycle_id

            # Find all meeting members for this parent in this cycle
            parent_members = self.env['pti.meeting.member'].search([
                ('partner_id', '=', parent.id),
                ('is_parent', '=', True),
            ])

            # Pre-fetch aps.student level data keyed by partner_id
            all_connected_ids = set()
            for member in parent_members:
                if member.meeting_id:
                    all_connected_ids.update(member.meeting_id.connected_partner_ids.ids)
            aps_level_map = {}  # partner_id -> level short_name
            if all_connected_ids and 'aps.student' in self.env:
                aps_students = self.env['aps.student'].search(
                    [('partner_id', 'in', list(all_connected_ids))]
                )
                for s in aps_students:
                    lvl = s.level_id
                    aps_level_map[s.partner_id.id] = (
                        lvl.short_name or lvl.name
                    ) if lvl else ''

            # Collect meetings with their time slot info
            meetings_data = []
            for member in parent_members:
                meeting = member.meeting_id
                if not meeting:
                    continue

                # Find the booked partner time slot linking meeting to a cycle slot
                pts = self.env['pti.partner.time.slot'].search([
                    ('meeting_id', '=', meeting.id),
                    ('status', '=', 'booked'),
                    ('time_slot_id.meeting_cycle_id', '=', cycle.id),
                ], limit=1)
                if not pts:
                    continue

                time_slot = pts.time_slot_id
                start_utc = time_slot.start_date_time
                end_utc = time_slot.end_date_time
                date_time_display = ''
                sort_key = start_utc or False
                if start_utc and end_utc:
                    start_local = pytz.utc.localize(start_utc).astimezone(user_tz)
                    end_local = pytz.utc.localize(end_utc).astimezone(user_tz)
                    date_str = f"{start_local.strftime('%a')} {utils.fmt_date(start_local)}"
                    time_str = f"{utils.fmt_time(start_local)}\u2013{utils.fmt_time(end_local)}"
                    date_time_display = f"{date_str} {time_str}"

                # Teachers
                teachers = []
                for m in meeting.member_ids.filtered(lambda m: m.is_teacher):
                    teachers.append({
                        'partner': m.partner_id,
                        'initials': utils.get_initials(m.partner_id.name),
                    })

                # Students (connected partners)
                students = []
                for student in meeting.connected_partner_ids:
                    students.append({
                        'partner': student,
                        'initials': utils.get_initials(student.name),
                        'level': aps_level_map.get(student.id, ''),
                    })

                meetings_data.append({
                    'sort_key': sort_key,
                    'date_time_display': date_time_display,
                    'teachers': teachers,
                    'students': students,
                })

            # Sort by date/time
            meetings_data.sort(key=lambda m: m['sort_key'] or datetime.min)

            # Collect all unique students across meetings for the header
            seen_student_ids = set()
            all_students = []
            for md in meetings_data:
                for s in md['students']:
                    if s['partner'].id not in seen_student_ids:
                        seen_student_ids.add(s['partner'].id)
                        all_students.append(s)

            report_data.append({
                'parent': parent,
                'parent_initials': utils.get_initials(parent.name),
                'cycle': cycle,
                'all_students': all_students,
                'meetings': meetings_data,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'pti.parent.meeting.summary',
            'docs': summaries,
            'report_data': report_data,
        }
