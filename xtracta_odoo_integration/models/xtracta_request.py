# -*- coding: utf-8 -*-
import requests
import logging
from odoo import _
import xml.etree.ElementTree as etree
from odoo.exceptions import ValidationError
from odoo.addons.xtracta_odoo_integration.models.response import Response

_logger = logging.getLogger('Xtracta')


def prepare_api_url(configure_obj, service):
    # hostname https://api-app.xtracta.com
    hostname = configure_obj and configure_obj.xtracta_api
    if not hostname:
        raise ValidationError(_('Please Provide Hostname In Configuration'))
    if service == 'get_columns':
        return '%s/v1/databases/columns' % hostname
    if service == 'data_add':
        return '%s/v1/databases/data_add' % hostname
    if service == 'get_document':
        return '%s/v1/documents' % hostname
    if service == 'update_document':
        return '%s/v1/documents/update'
    if service == 'get_database_data':
        return '%s/v1/databases/data' % hostname
    if service == 'data_update':
        return '%s/v1/databases/data_update' % hostname


def prepare_product_xml(root_tag, column_id, customer_obj, contact_type):
    """
    :param root_tag:  root tag of xml request body
    :param column_id:  column obj of xtracta table
    :param customer_obj: odoo customer object
    :param contact_type: contact type of customer
    :return: prepare xml only
    """
    for column in column_id:
        root_column = etree.SubElement(root_tag, 'column')
        root_column.attrib['name'] = column.column_name

        if column.customer_field.ttype == 'many2one':
            name = customer_obj[column.customer_field['name']]['display_name']
            root_column.text = "{}".format(name or ' ')
        elif contact_type and column.customer_field['name'] == 'type':
            root_column.text = "{}".format(contact_type)
        elif column.customer_field.name == 'parent_name':
            parent_name = customer_obj[column.customer_field['name']]
            if not parent_name:
                parent_name = "{}".format(customer_obj['name'])
            root_column.text = "{}".format(parent_name or ' ')
        elif column.customer_field.name == 'company_code':
            company_code = customer_obj.parent_id.company_code if customer_obj.parent_id else customer_obj.company_code
            root_column.text = "{}".format(company_code or " ")
        else:
            root_column.text = "{}".format(customer_obj[column.customer_field['name']] or ' ')


class XtractaRequest():

    def send_request(service, request_body, configure_obj):
        """
        send request api request to xtracta
        :param request_body:
        :return:  response data
        """
        success_flag = True
        api_url = prepare_api_url(configure_obj=configure_obj, service=service)
        try:
            response_data = requests.request(method='POST', url=api_url, data=request_body)
        except Exception as error:
            success_flag = False
            return success_flag, api_url, error
        if response_data.status_code in [200, 201]:
            response_data = Response(response_data)
            response_data = response_data.dict()
            return success_flag, api_url, response_data
        else:
            success_flag = False
            return success_flag, api_url, response_data.text

    def prepare_xml_request(self, process_obj, table_type, xtracta_log_id):
        """
        prepare xml request for xtracta api  service
        """
        database_id = process_obj and process_obj.xtracta_database_id
        xtracta_column_id = self.env['xtracta.columns'].search(
            ['&', ('xtracta_database_id', '=', process_obj.id), ('column_database_id', '=', database_id)])
        # check column without field set
        if not xtracta_column_id:
            msg = "THERE ARE NO COLUMN IN {}".format(process_obj.name)
            process_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                          request_data=False,
                                                          response_data=False, process_data=False, url=False,
                                                          error_message=False)
            return False
        if table_type == 'product':
            malicious_column = [column.column_name for column in xtracta_column_id if not column.product_field]
            if malicious_column:
                msg = "Please Select Product Filed On {} Column \n {}".format(', '.join(malicious_column))
                process_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                              request_data=False,
                                                              response_data=False, process_data=msg, url=False,
                                                              error_message=False)
                return False
        elif table_type == 'customer':
            malicious_column = [column.column_name for column in xtracta_column_id if not column.customer_field]
            if malicious_column:
                msg = "Please Select Customer Filed On Column \n {}".format(', '.join(malicious_column))
                process_obj.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                              request_data=False,
                                                              response_data=False, process_data=msg, url=False,
                                                              error_message=False)
                return False

        # prepare xml request
        if table_type == 'product':
            root_xml = etree.Element('xml')
            for obj in self:
                root_row = etree.SubElement(root_xml, 'row')
                for column in xtracta_column_id:
                    root_column = etree.SubElement(root_row, 'column')
                    root_column.attrib['name'] = column.column_name
                    if column.product_field.ttype == 'many2one':
                        name = obj[column.product_field['name']]['display_name']
                        root_column.text = "{}".format(name or ' ')
                    elif column.product_field.name == 'name':
                        # version 14.31.12.2021
                        # if found name field
                        # concat product name with his variant name
                        if obj and obj.product_template_attribute_value_ids:
                            variant = obj.product_template_attribute_value_ids._get_combination_name()
                            name = variant and "%s (%s)" % (obj.name, variant) or obj.name
                            root_column.text = name
                        else:
                            root_column.text = "{}".format(obj[column.product_field['name']] or ' ')
                    else:
                        root_column.text = "{}".format(obj[column.product_field['name']] or ' ')
            return etree.tostring(root_xml).decode()
        elif table_type == 'customer':
            root_xml = etree.Element('xml')
            for obj in self:
                # check for delivery address
                if obj.child_ids:  # (If customer has child ids)
                    #delivery_address = obj.child_ids.filtered(lambda child_ids: child_ids.type == 'delivery')
                    delivery_address = self.env['res.partner'].search([('id','=',obj.id),('type','=','delivery')],limit=1)
                    #billing_address = obj.child_ids.filtered(lambda child_ids: child_ids.type == 'invoice')
                    billing_address = self.env['res.partner'].search([('id', '=', obj.id), ('type', '=', 'invoice')],
                                                                      limit=1)
                    if delivery_address:
                        root_row = etree.SubElement(root_xml, 'row')
                        prepare_product_xml(root_tag=root_row, column_id=xtracta_column_id,
                                            customer_obj=delivery_address, contact_type=False)
                    else:
                        root_row = etree.SubElement(root_xml, 'row')
                        prepare_product_xml(root_tag=root_row, column_id=xtracta_column_id, customer_obj=obj,
                                            contact_type='delivery')
                    if billing_address:
                        root_row = etree.SubElement(root_xml, 'row')
                        prepare_product_xml(root_tag=root_row, column_id=xtracta_column_id,
                                            customer_obj=billing_address, contact_type=False)
                    else:
                        root_row = etree.SubElement(root_xml, 'row')
                        prepare_product_xml(root_tag=root_row, column_id=xtracta_column_id, customer_obj=obj,
                                            contact_type='billing')
                else:
                    delivery_address_row = etree.SubElement(root_xml, 'row')
                    prepare_product_xml(root_tag=delivery_address_row, column_id=xtracta_column_id, customer_obj=obj,
                                        contact_type='delivery')
                    billing_address_row = etree.SubElement(root_xml, 'row')
                    prepare_product_xml(root_tag=billing_address_row, column_id=xtracta_column_id, customer_obj=obj,
                                        contact_type='billing')

            return etree.tostring(root_xml).decode()
        return False
