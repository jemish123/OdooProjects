# -*- coding: utf-8 -*-
from odoo import fields, models


class XtractaColumns(models.Model):
    _name = 'xtracta.columns'
    _rec_name = 'column_name'
    _description = ' Xtracta Columns'

    def _get_customer_field(self):
        res_partner = self.env['ir.model'].search([('model', '=', 'res.partner')])
        return [('model_id', '=', res_partner.id)]

    def _get_product_field(self):
        res_partner = self.env['ir.model'].search([('model', '=', 'product.product')])
        return [('model_id', '=', res_partner.id)]

    column_id = fields.Char(string='Column Id')
    column_name = fields.Char(string='Column Name')
    column_group_id = fields.Char(string='Column Group Id')
    column_database_id = fields.Char(string='Column Database Id')
    xtracta_database_id = fields.Many2one('xtracta.database', string='Xtracta Database')
    product_field = fields.Many2one('ir.model.fields', string='Product Field', domain=_get_product_field)
    customer_field = fields.Many2one('ir.model.fields', string='Customer Field', domain=_get_customer_field)
    table_type = fields.Selection(related='xtracta_database_id.xtracta_table_type', string='Table Type')
