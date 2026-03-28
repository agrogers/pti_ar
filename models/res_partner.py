from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    pti_year_level = fields.Selection(
        selection=[
            ('prep', 'Prep'),
            ('1', 'Year 1'),
            ('2', 'Year 2'),
            ('3', 'Year 3'),
            ('4', 'Year 4'),
            ('5', 'Year 5'),
            ('6', 'Year 6'),
            ('7', 'Year 7'),
            ('8', 'Year 8'),
            ('9', 'Year 9'),
            ('10', 'Year 10'),
            ('11', 'Year 11'),
            ('12', 'Year 12'),
        ],
        string='Year Level',
    )
    pti_gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('non_binary', 'Non-binary'),
            ('other', 'Other'),
        ],
        string='Gender',
    )
