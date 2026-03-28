from odoo import fields, models, tools


class TeacherMeetingSummary(models.Model):
    _name = 'pti.teacher.meeting.summary'
    _description = 'Teacher Meeting Summary'
    _auto = False
    _order = 'teacher_id'

    teacher_id = fields.Many2one('res.partner', string='Teacher', readonly=True)
    meeting_cycle_id = fields.Many2one('pti.meeting.cycle', string='Meeting Cycle', readonly=True)
    meeting_count = fields.Integer(string='Interviews Scheduled', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    pts.partner_id AS teacher_id,
                    cts.meeting_cycle_id AS meeting_cycle_id,
                    COUNT(pts.id) AS meeting_count
                FROM pti_partner_time_slot pts
                JOIN pti_cycle_time_slot cts ON cts.id = pts.time_slot_id
                WHERE pts.status = 'booked'
                  AND pts.meeting_id IS NOT NULL
                GROUP BY pts.partner_id, cts.meeting_cycle_id
            )
        """ % self._table)
