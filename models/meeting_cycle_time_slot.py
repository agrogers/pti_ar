from odoo import api, fields, models


class MeetingCycleTimeSlot(models.Model):
    _name = 'pti.meeting.cycle.time.slot'
    _description = 'PTI Meeting Cycle Time Slot'
    _order = 'start_date_time'

    meeting_cycle_id = fields.Many2one(
        'pti.meeting.cycle',
        string='Meeting Cycle',
        required=True,
        ondelete='cascade',
    )
    start_date_time = fields.Datetime(string='Start Date/Time', required=True)
    end_date_time = fields.Datetime(string='End Date/Time', required=True)
    manually_adjusted = fields.Boolean(string='Manually Adjusted', default=False)
    partner_time_slot_ids = fields.One2many(
        'pti.partner.time.slot',
        'time_slot_id',
        string='Bookings',
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('meeting_cycle_id', 'start_date_time', 'end_date_time')
    def _compute_display_name(self):
        for record in self:
            cycle = record.meeting_cycle_id.name or ''
            start = record.start_date_time
            end = record.end_date_time
            if start and end:
                record.display_name = f"{cycle}: {fields.Datetime.to_string(start)} – {fields.Datetime.to_string(end)}"
            else:
                record.display_name = cycle or ''
