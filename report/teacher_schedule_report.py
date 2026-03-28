import pytz

from odoo import api, models

from ..models import utils


class TeacherScheduleReport(models.AbstractModel):
    _name = 'report.pti_ar.teacher_schedule_report'
    _description = 'Teacher Schedule Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        summaries = self.env['pti.teacher.meeting.summary'].browse(docids)
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        report_data = []

        for summary in summaries:
            teacher = summary.teacher_id
            cycle = summary.meeting_cycle_id

            # Get ALL time slots for this cycle (sorted by start time)
            all_cycle_slots = self.env['pti.cycle.time.slot'].search([
                ('meeting_cycle_id', '=', cycle.id),
            ], order='start_date_time')

            # Index teacher's booked partner time slots by cycle slot id
            partner_slots = self.env['pti.partner.time.slot'].search([
                ('partner_id', '=', teacher.id),
                ('time_slot_id.meeting_cycle_id', '=', cycle.id),
                ('status', '=', 'booked'),
                ('meeting_id', '!=', False),
            ])
            pts_by_slot = {pts.time_slot_id.id: pts for pts in partner_slots}

            slots_data = []
            current_date_str = None
            for time_slot in all_cycle_slots:
                # Format date and time in user timezone
                start_utc = time_slot.start_date_time
                end_utc = time_slot.end_date_time
                date_display = ''
                time_display = ''
                if start_utc and end_utc:
                    start_local = pytz.utc.localize(start_utc).astimezone(user_tz)
                    end_local = pytz.utc.localize(end_utc).astimezone(user_tz)
                    date_display = f"{start_local.strftime('%a')} {utils.fmt_date(start_local)}"
                    time_display = f"{utils.fmt_time(start_local)}\u2013{utils.fmt_time(end_local)}"

                # Show date only on first row of each new day
                show_date = date_display != current_date_str
                current_date_str = date_display

                # Determine slot status
                slot_state = time_slot.state  # 'available' or 'unavailable'
                pts = pts_by_slot.get(time_slot.id)
                meeting = pts.meeting_id if pts else None

                students_data = []
                parents_observers = []
                notes = ''
                if meeting:
                    status = 'booked'
                    # Connected students (the students the meeting is about)
                    for student in meeting.connected_partner_ids:
                        students_data.append({
                            'partner': student,
                            'initials': utils.get_initials(student.name),
                        })
                    # Parents and observers from members
                    for m in meeting.member_ids.filtered(lambda m: m.is_parent):
                        parents_observers.append({'name': m.partner_id.name, 'role': ''})
                    for m in meeting.member_ids.filtered(lambda m: m.is_observer):
                        parents_observers.append({'name': m.partner_id.name, 'role': 'Observer'})
                    notes = meeting.notes or ''
                elif slot_state == 'unavailable':
                    status = 'unavailable'
                else:
                    status = 'available'

                slots_data.append({
                    'date_display': date_display if show_date else '',
                    'time_display': time_display,
                    'status': status,
                    'students': students_data,
                    'parents_observers': parents_observers,
                    'notes': notes,
                })

            report_data.append({
                'teacher': teacher,
                'teacher_initials': utils.get_initials(teacher.name),
                'cycle': cycle,
                'slots': slots_data,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'pti.teacher.meeting.summary',
            'docs': summaries,
            'report_data': report_data,
        }
