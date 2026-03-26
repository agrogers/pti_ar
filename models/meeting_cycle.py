from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import utils


class MeetingCycle(models.Model):
    _name = 'pti.meeting.cycle'
    _description = 'PTI Meeting Cycle'
    _order = 'start_date desc'

    name = fields.Char(string='Name', required=True)
    short_name = fields.Char(string='Short Name', size=20)
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
        'pti.cycle.time.slot',
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

    @api.depends('name', 'short_name', 'start_date', 'end_date')
    def _compute_display_name(self):
        for record in self:
            label = record.short_name or record.name or ''
            if record.start_date and record.end_date:
                start = utils.fmt_date(record.start_date)
                end = utils.fmt_date(record.end_date)
                record.display_name = f"{label}: {start}-{end}"
            else:
                record.display_name = label

    def action_generate_time_slots(self):
        for cycle in self:
            if not cycle.start_date or not cycle.end_date:
                raise UserError("Please set both Start Date and End Date before generating time slots.")
            if cycle.start_date > cycle.end_date:
                raise UserError("Start Date must be before End Date.")
            if cycle.default_slot_length <= 0:
                raise UserError("Default Slot Length must be greater than 0.")
            if cycle.default_start_time >= cycle.default_finish_time:
                raise UserError("Default Start Time must be before Default Finish Time.")

            # Remove existing auto-generated slots; preserve manually adjusted ones
            cycle.time_slot_ids.filtered(lambda s: not s.manually_adjusted).unlink()

            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            slot_length = timedelta(minutes=cycle.default_slot_length)

            def _float_to_hm(val):
                h = int(val)
                m = int(round((val - h) * 60))
                return h, m

            start_h, start_m = _float_to_hm(cycle.default_start_time)
            finish_h, finish_m = _float_to_hm(cycle.default_finish_time)

            slots_to_create = []
            current_date = cycle.start_date
            while current_date <= cycle.end_date:
                slot_start = datetime.combine(current_date, time(start_h, start_m))
                day_end = datetime.combine(current_date, time(finish_h, finish_m))
                while slot_start + slot_length <= day_end:
                    slot_end = slot_start + slot_length
                    utc_start = user_tz.localize(slot_start).astimezone(pytz.utc).replace(tzinfo=None)
                    utc_end = user_tz.localize(slot_end).astimezone(pytz.utc).replace(tzinfo=None)
                    slots_to_create.append({
                        'meeting_cycle_id': cycle.id,
                        'start_date_time': utc_start,
                        'end_date_time': utc_end,
                    })
                    slot_start = slot_end
                current_date += timedelta(days=1)

            if slots_to_create:
                self.env['pti.cycle.time.slot'].create(slots_to_create)
