import secrets
import string

from odoo import fields, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pti_portal_access_code = fields.Char(
        string='PTI Portal Login Code',
        copy=False,
        index=True,
        groups='pti_ar.group_pti_manager',
    )

    _sql_constraints = [
        (
            'pti_portal_access_code_uniq',
            'unique(pti_portal_access_code)',
            'A PTI portal login code must be unique.',
        ),
    ]

    def action_generate_pti_portal_access_code(self):
        if not self.env.user.has_group('pti_ar.group_pti_manager'):
            raise AccessError('Only PTI managers can generate parent portal login codes.')

        alphabet = string.ascii_uppercase + string.digits
        Partner = self.sudo()
        for partner in self:
            code = ''.join(secrets.choice(alphabet) for _ in range(6))
            while Partner.search_count([
                ('pti_portal_access_code', '=', code),
                ('id', '!=', partner.id),
            ]):
                code = ''.join(secrets.choice(alphabet) for _ in range(6))
            partner.pti_portal_access_code = code
