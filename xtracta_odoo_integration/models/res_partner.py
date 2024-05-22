# -*- coding: utf-8 -*-
from odoo import fields, models, _
from .xtracta_request import XtractaRequest
import xml.etree.ElementTree as etree


class XtractaResPartner(models.Model):
    _inherit = 'res.partner'

    is_export_to_xtracta = fields.Boolean(string='Exported To Xtracta', copy=False)
    xtracta_database_id = fields.Many2one('xtracta.database', string='Xtracta Configuration', copy=False)
    xtracta_row_id = fields.Char(string='Xtracta Row Id', copy=False)

    def export_customer_xtracta(self, xtracta_obj, xtracta_log_id):
        """
        :param xtracta_obj: xtracta database object
        :param xtracta_log_id: xtracta log object id
        Export customer to xtracta
        """
        xml_body = XtractaRequest.prepare_xml_request(self=self, process_obj=xtracta_obj, table_type='customer',
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
                    #:TODO  filter only delivery and invoice address
                    if self.mapped('child_ids'):
                        self.mapped('child_ids').write(
                            {'is_export_to_xtracta': True, 'xtracta_database_id': xtracta_obj.id})
                    msg = "SUCCESSFULLY EXPORT CUSTOMERS"
                    xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='success', log_id=xtracta_log_id.id,
                                                                  request_data=request_data,
                                                                  response_data=response, process_data=False,
                                                                  url=api_url, error_message=False)
                    self._cr.commit()
                else:
                    msg = "ERROR TO EXPORT CUSTOMER"
                    xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                                  request_data=request_data,
                                                                  response_data=response, process_data=False,
                                                                  url=api_url, error_message=False)
            else:
                msg = "ERROR TO EXPORT CUSTOMER"
                xtracta_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                              request_data=request_data,
                                                              response_data=response, process_data=False, url=api_url, error_message=False)

    def write(self, vals):
        res = super(XtractaResPartner, self).write(vals)
        for customer in self:
            if customer.xtracta_database_id and customer.is_export_to_xtracta:
                xtracta_field = customer.env['xtracta.columns'].search(
                    [('xtracta_database_id', '=', customer.xtracta_database_id.id)]).mapped('customer_field.name')
                update_field = [x for x in vals.keys()]
                contain_xtracta_field = any(x in update_field for x in xtracta_field)
                if contain_xtracta_field:
                    if not customer.xtracta_row_id:
                        row_id = False
                        if not customer.parent_id:
                            row_id = customer.get_xtracta_customer_row_id(type=False)
                            customer.update_product_on_xtracta(vals=vals, xtracta_field=xtracta_field, row_id=row_id)
                        else:
                            if customer.type == 'delivery':
                                row_id = customer.get_xtracta_customer_row_id(type='delivery')
                                customer.update_product_on_xtracta(vals=vals, xtracta_field=xtracta_field, row_id=row_id)
                            elif customer.type == 'invoice':
                                row_id = customer.get_xtracta_customer_row_id(type='invoice')
                                customer.update_product_on_xtracta(vals=vals, xtracta_field=xtracta_field, row_id=row_id)
                            # else:
                            #     row_id = self.get_xtracta_customer_row_id(type=False)
                        if row_id:
                            customer.write({'xtracta_row_id': row_id})
                    else:
                        # customer already have a row id
                        customer.update_product_on_xtracta(vals=vals, xtracta_field=xtracta_field, row_id=customer.xtracta_row_id)
        return res

    def update_product_on_xtracta(self, vals, xtracta_field, row_id):
        """
        update product on xtracta
        """
        if row_id:
            body_data = self.prepare_xtracta_upd_body(vals=vals, xtracta_field=xtracta_field, row_id=row_id)
            success_flag, api_url, response = XtractaRequest.send_request(service='data_update',
                                                                          request_body=body_data,
                                                                          configure_obj=self.xtracta_database_id)
            if success_flag:
                status = response.get('databases_response') and response.get('databases_response').get('status')
                if status in ['200', '201']:
                    self.message_post(body="Successfully customer update on Xtracta")
        return True

    def prepare_xtracta_upd_body(self, vals, xtracta_field, row_id):
        """
         prepare dict for xtracta update body
        """
        database_id = self.xtracta_database_id if self.xtracta_database_id else self.parent_id and self.parent_id.xtracta_database_id
        root_xml = etree.Element('xml')
        for id in row_id.split(','):
            for field in [x for x in vals.keys()]:
                if field in xtracta_field:
                    value = vals[field]
                    if field == 'country_id':
                        value = self.env['res.country'].search([('id', '=', vals[field])]).name
                    elif field == 'state_id':
                        value = self.env['res.country.state'].search([('id', '=', vals[field])]).name
                    row_root = etree.SubElement(root_xml, 'row')
                    row_root.attrib['id'] = id
                    column_number = self.get_product_column_number(field_name=field)
                    column_root = etree.SubElement(row_root, 'column')
                    column_root.attrib['id'] = column_number
                    column_root.text = value
        xml_body = etree.tostring(root_xml).decode()
        update_body = {
            'api_key': database_id.xtracta_api_key,
            'database_id': database_id.xtracta_database_id,
            'data': xml_body
        }
        return update_body

    def get_xtracta_customer_row_id(self, type):
        """
        :param type: address type
        get xtracta customer row id
        """
        body_data = self.xtracta_get_data_body()
        success_flag, api_url, response = XtractaRequest.send_request(service='get_database_data',
                                                                      request_body=body_data,
                                                                      configure_obj=self.xtracta_database_id)
        if success_flag:
            row = response and response.get('databases_response') and response.get('databases_response').get(
                'data') and response.get('databases_response').get('data').get('row')
            if isinstance(row, list):
                id_ls = []
                for val in row:
                    # filter address by type
                    vals_ls = [data.get('value') for data in val.get('column')]
                    if type in vals_ls:
                        return val.get('_id')
                    elif type in vals_ls:
                        return val.get('_id')
                    id_ls.append(val and val.get('_id'))
                return ','.join(id_ls)
            else:
                return row.get('_id')
        else:
            return False

    def get_product_column_number(self, field_name):
        """
        :param  field_name Name  of the field
        """
        field_id = self.env['ir.model.fields'].search([('name', '=', field_name), ('model', '=', 'res.partner')])
        xtracta_column = self.env['xtracta.columns'].search([('xtracta_database_id', '=', self.xtracta_database_id.id),
                                                             ('customer_field', '=', field_id.id)])
        if xtracta_column:
            return xtracta_column.column_id

    def xtracta_get_data_body(self):
        """
        prepare dict for request data
        :return dictionary
        """
        # check if customer is self as parent use that own company code
        if not self.parent_id:
            company_code = self.company_code
        else:
            company_code = self.parent_id and self.parent_id.company_code
        # search company_code field and value
        company_code_field_id = self.env['ir.model.fields'].search(
            [('name', '=', 'company_code'), ('model', '=', 'res.partner')])
        xtracta_column_number = self.env['xtracta.columns'].search(
            [('xtracta_database_id', '=', self.xtracta_database_id.id),
             ('customer_field', '=', company_code_field_id.id)])

        if xtracta_column_number:
            column_number = xtracta_column_number and xtracta_column_number.column_id
            condition = "{}={}".format(column_number, company_code)
            request_data = {
                'api_key': self.xtracta_database_id and self.xtracta_database_id.xtracta_api_key,
                'database_id': self.xtracta_database_id and self.xtracta_database_id.xtracta_database_id,
                'conditions': condition
            }
            return request_data
