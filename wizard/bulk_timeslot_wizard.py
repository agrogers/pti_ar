from odoo import fields, models


class BulkTimeslotWizard(models.TransientModel):
    _name = 'pti.bulk.timeslot.wizard'
    _description = 'Bulk Add Time Slots for Teachers'

    teacher_ids = fields.Many2many(
        'res.partner',
        'pti_bulk_timeslot_wizard_teacher_rel',
        'wizard_id',
        'partner_id',
        string='Teachers',
        required=True,
    )
    time_slot_ids = fields.Many2many(
        'pti.cycle.time.slot',
        'pti_bulk_timeslot_wizard_slot_rel',
        'wizard_id',
        'slot_id',
        string='Time Slots',
        required=True,
        default=lambda self: self.env['pti.cycle.time.slot'].search([]),
    )

    def action_add_timeslots(self):
        PartnerTimeSlot = self.env['pti.partner.time.slot']
        teacher_ids = self.teacher_ids.ids
        slot_ids = self.time_slot_ids.ids

        existing = PartnerTimeSlot.search([
            ('partner_id', 'in', teacher_ids),
            ('time_slot_id', 'in', slot_ids),
        ])
        existing_pairs = {(rec.partner_id.id, rec.time_slot_id.id) for rec in existing}

        to_create = [
            {'partner_id': teacher_id, 'time_slot_id': slot_id, 'status': 'available'}
            for teacher_id in teacher_ids
            for slot_id in slot_ids
            if (teacher_id, slot_id) not in existing_pairs
        ]
        if to_create:
            PartnerTimeSlot.create(to_create)

        added_count = len(to_create)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Time Slots Added',
                'message': f'{added_count} time slot(s) added successfully.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
