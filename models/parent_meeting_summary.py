from odoo import fields, models, tools


class ParentMeetingSummary(models.Model):
    _name = 'pti.parent.meeting.summary'
    _description = 'Parent Meeting Summary'
    _auto = False
    _order = 'parent_id'

    parent_id = fields.Many2one('res.partner', string='Parent', readonly=True)
    meeting_cycle_id = fields.Many2one('pti.meeting.cycle', string='Meeting Cycle', readonly=True)
    meeting_count = fields.Integer(string='Interviews Scheduled', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    mm.partner_id AS parent_id,
                    cts.meeting_cycle_id AS meeting_cycle_id,
                    COUNT(DISTINCT mm.meeting_id) AS meeting_count
                FROM pti_meeting_member mm
                JOIN pti_partner_meeting pm ON pm.id = mm.meeting_id
                JOIN pti_partner_time_slot pts ON pts.meeting_id = pm.id
                JOIN pti_cycle_time_slot cts ON cts.id = pts.time_slot_id
                WHERE mm.is_parent = TRUE
                  AND pts.status = 'booked'
                GROUP BY mm.partner_id, cts.meeting_cycle_id
            )
        """ % self._table)
