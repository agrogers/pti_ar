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

            # Get all booked time slots for this teacher in this cycle
            partner_slots = self.env['pti.partner.time.slot'].search([
                ('partner_id', '=', teacher.id),
                ('time_slot_id.meeting_cycle_id', '=', cycle.id),
                ('status', '=', 'booked'),
                ('meeting_id', '!=', False),
            ])
            # Sort chronologically by the related time slot start
            partner_slots = partner_slots.sorted(
                key=lambda pts: pts.time_slot_id.start_date_time or ''
            )

            slots_data = []
            current_date_str = None
            for pts in partner_slots:
                meeting = pts.meeting_id
                time_slot = pts.time_slot_id

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

                # Get members by role
                students = meeting.member_ids.filtered(
                    lambda m: m.is_student
                ).mapped('partner_id')
                parents = meeting.member_ids.filtered(
                    lambda m: m.is_parent
                ).mapped('partner_id')
                observers = meeting.member_ids.filtered(
                    lambda m: m.is_observer
                ).mapped('partner_id')

                # Prepare student data with initials fallback
                students_data = []
                for student in students:
                    students_data.append({
                        'partner': student,
                        'initials': utils.get_initials(student.name),
                    })

                # Parents and observers combined list
                parents_observers = []
                for p in parents:
                    parents_observers.append({'name': p.name, 'role': ''})
                for o in observers:
                    parents_observers.append({'name': o.name, 'role': 'Observer'})

                slots_data.append({
                    'date_display': date_display if show_date else '',
                    'time_display': time_display,
                    'students': students_data,
                    'parents_observers': parents_observers,
                    'notes': meeting.notes or '',
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
