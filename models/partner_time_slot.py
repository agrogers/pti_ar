from odoo import api, fields, models


class PartnerTimeSlot(models.Model):
    _name = 'pti.partner.time.slot'
    _description = 'PTI Partner Time Slot'
    _order = 'time_slot_id'

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
    )
    time_slot_id = fields.Many2one(
        'pti.cycle.time.slot',
        string='Time Slot',
        required=True,
        ondelete='cascade',
    )
    status = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('booked', 'Booked'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Completed'),
        ],
        string='Status',
        default='available',
        required=True,
    )
    meeting_id = fields.Many2one(
        'pti.partner.meeting',
        string='Meeting',
        ondelete='set null',
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('partner_id', 'time_slot_id', 'status')
    def _compute_display_name(self):
        for record in self:
            partner = record.partner_id.name or ''
            slot = record.time_slot_id.display_name or ''
            status_label = dict(self._fields['status'].selection).get(record.status, record.status)
            record.display_name = f"{partner} – {slot} [{status_label}]" if partner else slot
