from odoo import api, fields, models


class MeetingMember(models.Model):
    _name = 'pti.meeting.member'
    _description = 'PTI Meeting Member'
    _order = 'meeting_id, partner_id'

    meeting_id = fields.Many2one(
        'pti.partner.meeting',
        string='Meeting',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
    )
    is_teacher = fields.Boolean(string='Is Teacher', default=False)
    is_parent = fields.Boolean(string='Is Parent', default=False)
    is_student = fields.Boolean(string='Is Student', default=False)
    is_observer = fields.Boolean(string='Is Observer', default=False)
    notes = fields.Text(string='Notes')

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('partner_id', 'meeting_id')
    def _compute_display_name(self):
        for record in self:
            partner = record.partner_id.name or ''
            meeting = record.meeting_id.display_name or f"#{record.meeting_id.id}"
            record.display_name = f"{partner} @ {meeting}" if partner else meeting
