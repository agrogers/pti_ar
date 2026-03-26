import pytz

from odoo import api, fields, models

from . import utils


class CycleTimeSlot(models.Model):
    _name = 'pti.cycle.time.slot'
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

    @api.depends('meeting_cycle_id', 'meeting_cycle_id.short_name', 'start_date_time', 'end_date_time')
    def _compute_display_name(self):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        for record in self:
            cycle = record.meeting_cycle_id
            label = cycle.short_name or cycle.name or ''
            start_utc = record.start_date_time
            end_utc = record.end_date_time
            if start_utc and end_utc:
                start_local = pytz.utc.localize(start_utc).astimezone(user_tz)
                end_local = pytz.utc.localize(end_utc).astimezone(user_tz)
                date_str = utils.fmt_date(start_local)
                time_str = f"{utils.fmt_time(start_local)}-{utils.fmt_time(end_local)}"
                record.display_name = f"{label}: {date_str}: {time_str}"
            else:
                record.display_name = label
