# -*- coding: utf-8 -*-
from odoo import api, fields, models

class XtractaAccountMove(models.Model):
    _inherit = 'account.move'

    xtracta_instance_id = fields.Many2one('xtracta.database', string='Xtracta')