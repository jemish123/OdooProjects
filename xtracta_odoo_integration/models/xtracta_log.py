# -*- coding: utf-8 -*-
import datetime
from odoo import fields, models, api
from datetime import datetime, timedelta


class XtractaLog(models.Model):
    _name = 'xtracta.log'
    _description = 'xtracta log message'
    _order = 'id desc'

    name = fields.Char(string='Name')
    operation_name = fields.Selection([('get_document', 'Get The List Of Document'), ('get_order_data', 'Get The '
                                                                                                        'Order Data '
                                                                                                        'From '
                                                                                                        'Document')],
                                      string='Operation')
    operation_type = fields.Selection([('export', 'Export'), ('import', 'Import')])
    xtracta_operation_type = fields.Selection([('product', 'Product'), ('order', 'Orders'), ('customer', 'Customer')])
    instance_id = fields.Many2one('xtracta.database', string='Instance')
    xtracta_log_ids = fields.One2many('xtracta.log.line', 'xtracta_log_id', string='Xtracta Log Line')
    document_no = fields.Char(string='Document Number')

    @api.model
    def create(self, vals_list):
        seq = self.env.ref('xtracta_odoo_integration.seq_process_detail')
        name = seq and seq.next_by_id()
        vals_list.update({'name': name})
        return super(XtractaLog, self).create(vals_list)

    def auto_delete_log_message(self):
        """
        Auto delete log message through crone process
        """
        for obj in self.search([('create_date', '<', datetime.now() - timedelta(days=30))],limit=500):
            obj.xtracta_log_ids.unlink()
            obj.unlink()


class XtractaLogLine(models.Model):
    _name = 'xtracta.log.line'
    _rec_name = 'log_message'

    log_message = fields.Text(string='Log Message')
    operation_status = fields.Selection([('success', 'Success'), ('fail', 'Error')], string='Operation Status')
    xtracta_log_id = fields.Many2one('xtracta.log', string='Xtracta Log')
    xtracta_request_data = fields.Text(string='Request Data')
    xtracta_response_data = fields.Text(string='Response Data')
    process_data = fields.Text(string='Process Data')
    api_url = fields.Char(string="API URL")
    error_message = fields.Text(string="Error Message")