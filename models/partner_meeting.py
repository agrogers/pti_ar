from odoo import api, fields, models


class PartnerMeeting(models.Model):
    _name = 'pti.partner.meeting'
    _description = 'PTI Partner Meeting'
    _order = 'id desc'

    status = fields.Selection(
        selection=[
            ('scheduled', 'Scheduled'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='scheduled',
        required=True,
    )
    observer_partner_ids = fields.Many2many(
        'res.partner',
        'pti_partner_meeting_observer_rel',
        'meeting_id',
        'partner_id',
        string='Observer Partners',
    )
    connected_partner_ids = fields.Many2many(
        'res.partner',
        'pti_partner_meeting_connected_rel',
        'meeting_id',
        'partner_id',
        string='Connected Partners',
    )
    notes = fields.Text(string='Notes')
    actual_start_time = fields.Float(string='Actual Start Time')
    actual_finish_time = fields.Float(string='Actual Finish Time')
    location = fields.Char(string='Location')
    member_ids = fields.One2many(
        'pti.meeting.member',
        'meeting_id',
        string='Members',
    )
    partner_time_slot_ids = fields.One2many(
        'pti.partner.time.slot',
        'meeting_id',
        string='Time Slots',
    )
    scheduled_start = fields.Datetime(
        string='Scheduled Start',
        compute='_compute_scheduled_times',
        store=True,
    )
    scheduled_end = fields.Datetime(
        string='Scheduled End',
        compute='_compute_scheduled_times',
        store=True,
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends(
        'partner_time_slot_ids.time_slot_id.start_date_time',
        'partner_time_slot_ids.time_slot_id.end_date_time',
    )
    def _compute_scheduled_times(self):
        for record in self:
            slots = record.partner_time_slot_ids.mapped('time_slot_id')
            starts = slots.mapped('start_date_time')
            ends = slots.mapped('end_date_time')
            record.scheduled_start = min(starts) if starts else False
            record.scheduled_end = max(ends) if ends else False

    @api.depends('connected_partner_ids', 'status')
    def _compute_display_name(self):
        for record in self:
            partners = ', '.join(record.connected_partner_ids.mapped('name'))
            status_label = dict(self._fields['status'].selection).get(record.status, record.status)
            if partners:
                record.display_name = f"{partners} [{status_label}]"
            else:
                record.display_name = f"Meeting #{record.id} [{status_label}]"
