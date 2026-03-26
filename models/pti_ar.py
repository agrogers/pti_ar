from odoo import api, fields, models


class PtiAr(models.Model):
    _name = 'pti.ar'
    _description = 'PTI AR'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
