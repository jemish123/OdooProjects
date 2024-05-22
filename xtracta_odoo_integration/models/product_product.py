# -*- coding: utf-8 -*-
from odoo import fields, models, _
from .xtracta_request import XtractaRequest
import xml.etree.ElementTree as etree


class XtractaProduct(models.Model):
    _inherit = 'product.product'

    is_export_to_xtracta = fields.Boolean(string='Exported To Xtracta', default=False, copy=False)
    xtracta_database_id = fields.Many2one('xtracta.database', string='Xtracta Configuration', copy=False)
    xtracta_account_id = fields.Char(string='Account Number', copy=False)
    xtracta_row_id = fields.Char(string='Xtracta Row Id', copy=False)

    def export_product_xtracta(self, xtracta_obj, xtracta_log_id):
        """
        :param xtracta_obj: xtracta database object
        :param xtracta_log_id: xtracta log operation id
        export product to xtracta
        """
        xml_body = XtractaRequest.prepare_xml_request(self=self, process_obj=xtracta_obj, table_type='product',
                                                      xtracta_log_id=xtracta_log_id)
        if xml_body:
            request_data = {
                'api_key': "{}".format(xtracta_obj.xtracta_api_key),
                'database_id': "{}".format(xtracta_obj.xtracta_database_id),
                'data': xml_body
            }
            success_flag, api_url, response = XtractaRequest.send_request(service='data_add', request_body=request_data,
                                                                          configure_obj=xtracta_obj)
            if success_flag and response:
                db_response = response and response.get('databases_response')
                status = db_response and db_response['status']
                if status == '200':
                    self.write({'is_export_to_xtracta': True, 'xtracta_database_id': xtracta_obj.id})
                    msg = "SUCCESSFULLY EXPORT PRODUCT"
                    xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='success', log_id=xtracta_log_id.id,
                                                                  request_data=request_data,
                                                                  response_data=response, process_data=False,
                                                                  url=api_url, error_message=False)
                    self._cr.commit()
                else:
                    msg = "ERROR TO EXPORT PRODUCT"
                    xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                                  request_data=request_data,
                                                                  response_data=response, process_data=False,
                                                                  url=api_url, error_message=False)
            else:
                msg = "ERROR TO EXPORT PRODUCT"
                xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                              request_data=request_data,
                                                              response_data=response, process_data=False,
                                                              url=api_url, error_message=False)
    def write(self, values):
        res = super(XtractaProduct, self).write(values)
        for product in self:
            if product.xtracta_database_id and product.is_export_to_xtracta :
                xtracta_field = self.env['xtracta.columns'].search(
                    [('xtracta_database_id', '=', product.xtracta_database_id.id)]).mapped('product_field.name')
                update_field = [x for x in values.keys()]
                contain_xtracta_field = any(x in update_field for x in xtracta_field)
                if contain_xtracta_field:
                    if not product.xtracta_row_id:
                        row_id = product.get_xtracta_product_row_id()
                        if row_id:
                            product.update_xtracta_product(vals=values, xtracta_field=xtracta_field, row_id=row_id)
                    else:
                        product.update_xtracta_product(vals=values, xtracta_field=xtracta_field,
                                                         row_id=product.xtracta_row_id)
        return res

    def get_xtracta_product_row_id(self):
        """
        fetch product row id using Product SKU
        """
        request_body = self.body_data_xtracta_row_id()
        if request_body:
            success_flag, api_url, response = XtractaRequest.send_request(service='get_database_data',
                                                                          request_body=request_body,
                                                                          configure_obj=self.xtracta_database_id)
            if success_flag:
                row = response and response.get('databases_response') and response.get('databases_response').get(
                    'data') and response.get('databases_response').get('data').get('row')
                if isinstance(row, dict):
                    row_id = row and row.get('_id')
                    self.xtracta_row_id = row_id
                    return row_id
        return False

    def update_xtracta_product(self, vals, xtracta_field, row_id):
        request_body = self.prepare_xtracta_product_body(vals=vals, xtracta_field=xtracta_field, row_id=row_id)
        success_flag, api_url, response = XtractaRequest.send_request(service='data_update',
                                                                      request_body=request_body,
                                                                      configure_obj=self.xtracta_database_id)
        if success_flag:
            status = response.get('databases_response') and response.get('databases_response').get('status')
            if status in ['200', '201']:
                self.message_post(body="Successfully customer update on Xtracta")
        return True

    def prepare_xtracta_product_body(self, vals, xtracta_field, row_id):
        root_xml = etree.Element('xml')
        for field in [x for x in vals.keys()]:
            if field in xtracta_field:
                value = vals[field]
                row_root = etree.SubElement(root_xml, 'row')
                row_root.attrib['id'] = row_id
                column_number = self.get_product_column_number(field_name=field)
                column_root = etree.SubElement(row_root, 'column')
                column_root.attrib['id'] = column_number
                column_root.text = "{}".format(value)

        xml_body = etree.tostring(root_xml).decode()
        update_body = {
            'api_key': self.xtracta_database_id and self.xtracta_database_id.xtracta_api_key,
            'database_id': self.xtracta_database_id and self.xtracta_database_id.xtracta_database_id,
            'data': xml_body
        }
        return update_body

    def body_data_xtracta_row_id(self):
        sku_field_id = self.env['ir.model.fields'].search(
            [('name', '=', 'default_code'), ('model', '=', 'product.product')])
        xtracta_column_number = self.env['xtracta.columns'].search(
            [('product_field', '=', sku_field_id.id), ('xtracta_database_id', '=', self.xtracta_database_id.id)])
        if xtracta_column_number:
            column_number = xtracta_column_number and xtracta_column_number.column_id
            condition = "{}={}".format(column_number, self.default_code)
            request_data = {
                'api_key': self.xtracta_database_id and self.xtracta_database_id.xtracta_api_key,
                'database_id': self.xtracta_database_id and self.xtracta_database_id.xtracta_database_id,
                'conditions': condition
            }
            return request_data
        return False

    def get_product_column_number(self, field_name):
        """
        :param  field_name Name  of the field
        """
        field_id = self.env['ir.model.fields'].search([('name', '=', field_name), ('model', '=', 'product.product')])
        xtracta_column = self.env['xtracta.columns'].search([('xtracta_database_id', '=', self.xtracta_database_id.id),
                                                             ('product_field', '=', field_id.id)])
        if xtracta_column:
            return xtracta_column.column_id
