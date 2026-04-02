from odoo import fields, models, tools


class ParentMeetingSummary(models.Model):
    _name = 'pti.parent.meeting.summary'
    _description = 'Parent Meeting Summary'
    _auto = False
    _order = 'parent_id'

    parent_id = fields.Many2one('res.partner', string='Parent', readonly=True)
    meeting_cycle_id = fields.Many2one('pti.meeting.cycle', string='Meeting Cycle', readonly=True)
    meeting_count = fields.Integer(string='Interviews Scheduled', readonly=True)
    last_meeting_write_date = fields.Datetime(string='Last Updated', readonly=True)

    def action_view_meetings(self):
        self.ensure_one()
        members = self.env['pti.meeting.member'].search([
            ('partner_id', '=', self.parent_id.id),
            ('is_parent', '=', True),
        ])
        meeting_ids = members.mapped('meeting_id').filtered(
            lambda m: m.partner_time_slot_ids.filtered(
                lambda pts: pts.status == 'booked'
                and pts.time_slot_id.meeting_cycle_id.id == self.meeting_cycle_id.id
            )
        ).ids
        return {
            'type': 'ir.actions.act_window',
            'name': f'Meetings – {self.parent_id.name}',
            'res_model': 'pti.partner.meeting',
            'view_mode': 'list,form',
            'domain': [('id', 'in', meeting_ids)],
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    mm.partner_id AS parent_id,
                    cts.meeting_cycle_id AS meeting_cycle_id,
                    COUNT(DISTINCT mm.meeting_id) AS meeting_count,
                    MAX(pm.write_date) AS last_meeting_write_date
                FROM pti_meeting_member mm
                JOIN pti_partner_meeting pm ON pm.id = mm.meeting_id
                JOIN pti_partner_time_slot pts ON pts.meeting_id = pm.id
                JOIN pti_cycle_time_slot cts ON cts.id = pts.time_slot_id
                WHERE mm.is_parent = TRUE
                  AND pts.status = 'booked'
                GROUP BY mm.partner_id, cts.meeting_cycle_id
            )
        """ % self._table)
