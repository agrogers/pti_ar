from odoo import api, fields, models


class MeetingCycle(models.Model):
    _name = 'pti.meeting.cycle'
    _description = 'PTI Meeting Cycle'
    _order = 'start_date desc'

    name = fields.Char(string='Name', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    default_slot_length = fields.Integer(
        string='Default Slot Length (minutes)',
        default=15,
        required=True,
    )
    default_start_time = fields.Float(string='Default Start Time', default=9.0)
    default_finish_time = fields.Float(string='Default Finish Time', default=15.0)
    time_slot_ids = fields.One2many(
        'pti.meeting.cycle.time.slot',
        'meeting_cycle_id',
        string='Time Slots',
    )
    time_slot_count = fields.Integer(
        string='Time Slot Count',
        compute='_compute_time_slot_count',
    )

    @api.depends('time_slot_ids')
    def _compute_time_slot_count(self):
        for record in self:
            record.time_slot_count = len(record.time_slot_ids)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'start_date', 'end_date')
    def _compute_display_name(self):
        for record in self:
            if record.start_date and record.end_date:
                record.display_name = f"{record.name} ({record.start_date} – {record.end_date})"
            else:
                record.display_name = record.name or ''
