# -*- coding: utf-8 -*-
import pprint
import logging
from odoo import fields, models, _, api
from .xtracta_request import XtractaRequest

_logger = logging.getLogger('Xtracta')


class XtractaDatabase(models.Model):
    _name = 'xtracta.database'
    _description = 'xtracta database'

    name = fields.Char(string='Xtracta Database')
    xtracta_api = fields.Char(string='Xtracta API URL', default='https://api-app.xtracta.com')
    xtracta_api_key = fields.Char(string='Xtracta API KEY')
    xtracta_database_id = fields.Char(string='Xtracta Database ID')
    
    xtracta_table_type = fields.Selection([('product', 'Product'), ('customer', 'Customer'), ('order', 'Order')],
                                          string='Xtracta Table Type')

    total_customer = fields.Integer(string='Total Customer', compute='get_kanban_counts')
    total_product = fields.Integer(string='Total Product', compute='get_kanban_counts')
    total_order = fields.Integer(string='Total Order', compute='get_kanban_counts')
    color = fields.Integer(string='Color Index', help="select color")

    xtracta_workflow_id = fields.Char(string='Xtracta WorkFlow ID')
    xtracta_document_status = fields.Selection([('no value', 'no value'), ('pre-processing', 'pre processing'),
                                                ('indexing', 'indexing'), ('qa', 'qa'), ('reject', 'reject'),
                                                ('output', 'output'), ('output-in-progress', 'output in progress'),
                                                ('api-ui-in-progress', 'api ui in progress')],
                                               string='Xtracta Document Status')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    xtracta_default_obj = fields.Boolean(string='Set As Default')
    tax_id = fields.Many2many('account.tax', string='Default tax')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    xtracta_account_income_categ_id = fields.Many2one('account.account', string='Income Account')

    xtracta_account_expense_categ_id = fields.Many2one('account.account', company_dependent=True,
                                                       string="Expense Account")
    team_id = fields.Many2one('crm.team', string='Sales Team')
    api_download_status = fields.Selection([('archived', 'Archived'), ('active', 'Active')],
                                           string='API Download Status')

    def import_columns(self):
        """
        Import all columns from xtracta and save into Odoo
        """
        request_body = {
            'api_key': "{}".format(self.xtracta_api_key),
            'database_id': "{}".format(self.xtracta_database_id)
        }
        success_flag, api_url, response = XtractaRequest.send_request(service='get_columns', request_body=request_body,
                                                                      configure_obj=self)
        if isinstance(response, dict):
            column = response and response.get('databases_response') and response.get('databases_response').get(
                'column')
            if isinstance(column, list):
                xtracta_cl = self.env['xtracta.columns']
                for value in column:
                    column_id = value and value.get('id')
                    
                    # prepare dict for orm process
                    data = {
                        'column_id': column_id,
                        'column_name': value and value.get('name'),
                        'column_group_id': value and value.get('group_id'),
                        'column_database_id': value and value.get('database_id'),
                        'xtracta_database_id': self.id
                    }
                    exist_record = xtracta_cl.search(['&', ('column_id', '=', column_id), ('column_database_id', '=',
                                                                                           value and value.get(
                                                                                               'database_id'))])
                    if exist_record:
                        exist_record.write(data)
                        _logger.info("[UPDATE] Columns {}".format(value and value.get('name')))
                    else:
                        xtracta_cl.create(data)
                        _logger.info("[CREATE]  Columns {}".format(value and value.get('name')))
                self._cr.commit()
        return True

    def get_kanban_counts(self):
        for data in self:
            data.total_customer = self.env['res.partner'].sudo().search_count(
                ['&', ('is_export_to_xtracta', '=', True), ('xtracta_database_id', '=', data.id)])
            data.total_product = self.env['product.product'].sudo().search_count(
                ['&', ('is_export_to_xtracta', '=', True), ('xtracta_database_id', '=', data.id)])
            data.total_order = self.env['sale.order'].sudo().search_count(
                [('xtracta_configuration_id', '=', data.id)]
            )

    def action_redirect_to_product(self):
        action = self.env.ref('product.product_normal_action_sell').read()[0]
        action['domain'] = [('xtracta_database_id', '=', self.id)]
        return action

    def action_redirect_to_customer(self):
        action = self.env.ref('xtracta_odoo_integration.xtracta_res_partner_action').read()[0]
        action['domain'] = [('xtracta_database_id', '=', self.id)]
        return action

    def action_redirect_to_column(self):
        action = self.env.ref('xtracta_odoo_integration.xtracta_columns_action').read()[0]
        action['domain'] = [('xtracta_database_id', '=', self.id)]
        return action

    def action_redirect_to_order(self):
        action = self.env.ref('xtracta_odoo_integration.xtracta_sale_order_action').read()[0]
        action['domain'] = [('xtracta_configuration_id', '=', self.id)]
        return action

    def action_redirect_to_log(self):
        action = self.env.ref('xtracta_odoo_integration.xtracta_log_action').read()[0]
        action['domain'] = [('instance_id', '=', self.id)]
        return action

    def xtracta_open_instance_view(self):
        form_id = self.env.ref('xtracta_odoo_integration.xtracta_database_view_form')
        action = {
            'name': _('Xtracta Databse'),
            'view_id': False,
            'res_model': 'xtracta.database',
            'context': self._context,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(form_id.id, 'form')],
            'type': 'ir.actions.act_window',
        }
        return action

    def create_xtracta_log_operation(self, operation_name, operation_type, ins_id, document_no, op_type):
        operation_dict = {
            'operation_name': operation_name,
            'operation_type': operation_type,
            'instance_id': ins_id,
            'document_no': document_no,
            'xtracta_operation_type': op_type
        }
        xtracta_log_id = self.env['xtracta.log'].create(operation_dict)
        self._cr.commit()
        return xtracta_log_id

    def create_xtracta_log_line_operation(self, msg, status, log_id, request_data, response_data, process_data, url,
                                          error_message):
        log_line_dict = {
            'log_message': msg,
            'operation_status': status,
            'xtracta_log_id': log_id,
            'xtracta_request_data': pprint.pformat(request_data) if request_data else False,
            'xtracta_response_data': pprint.pformat(response_data) if response_data else False,
            'process_data': pprint.pformat(process_data) if process_data else False,
            'api_url': url if url else False,
            'error_message': pprint.pformat(error_message) if error_message else False
        }
        self.env['xtracta.log.line'].create(log_line_dict)

    def import_orders(self):
        """
        import all order from xtracta and save into odoo
        """
        commit_time_flg = 0
        request_body = {
            'api_key': "{}".format(self.xtracta_api_key),
            'workflow_id': "{}".format(self.xtracta_workflow_id),
            'document_status': "{}".format(self.xtracta_document_status)
        }

        if self.api_download_status:
            request_body.update({'api_download_status': self.api_download_status})
        # create Xtracta log
        xtracta_log_id = self.create_xtracta_log_operation(operation_name='get_document',
                                                           operation_type='import', ins_id=self.id, document_no=False,
                                                           op_type='order')
        success_flag, api_url, response = XtractaRequest.send_request(service='get_document', request_body=request_body,
                                                                      configure_obj=self)
        if success_flag and isinstance(response, dict):
            status = response.get('documents_response') and response.get('documents_response').get('status')
            if status == '200':
                msg = "[DOCUMENT LIST] GET DOCUMENT LIST FROM XTRACTA"
                self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=xtracta_log_id.id,
                                                       request_data=request_body,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)

                document = response.get('documents_response') and response.get('documents_response').get('document')
                # get document id from API response
                if isinstance(document, list):
                    document_lst = [doc['document_id'] for doc in document if doc['document_id']]
                else:
                    document_lst = document.get('document_id', False)
                    if document_lst:
                        document_lst = [document_lst]
                # document_lst = [203636857]
                if document_lst:
                    for doc in document_lst:
                        commit_time_flg += 1
                        doc_log_id, sale_order_dict = self.get_sale_order_val_by_doc_id(doc_id=doc)
                        if sale_order_dict:
                            self.create_sale_order(order_data=sale_order_dict, log_id=doc_log_id)
                        if commit_time_flg > 10:
                            self._cr.commit()
                            commit_time_flg = 0
                else:
                    msg = "[NOT FOUND] DOCUMENT LIST NOT APPEAR IN RESPONSE"
                    self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                           request_data=request_body,
                                                           response_data=response, process_data=False, url=api_url,
                                                           error_message=False)
            else:
                msg = "[ERROR] NOT ABLE TO GET DATA FROM XTRACTA".format(api_url)
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                       request_data=request_body,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)
        else:
            msg = "[ERROR] NOT ABLE TO GET DATA FROM XTRACTA".format(api_url)
            self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                   request_data=request_body,
                                                   response_data=response, process_data=False, url=api_url,
                                                   error_message=False)

    def create_sale_order(self, order_data, log_id):
        """
        create sale order in odoo
        :param order_data xtracta order data dict
        """
        sale_order_obj = self.env['sale.order']

        customer_account_number = order_data.get('Account Number')
        document_id = order_data.get('document_id', False)
        document_url = order_data.get('document_url', False)
        order_line = order_data.get('order_line', False)

        # search customer in odoo
        if customer_account_number:
            partner_id = self.env['res.partner'].search([('company_code', '=', customer_account_number)])
            if not partner_id:
                msg = "[NOT FOUND] CUSTOMER NOT FOUND WITH {} ACCOUNT NUMBER".format(customer_account_number)
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=log_id.id,
                                                       request_data=False,
                                                       response_data=False, process_data=order_data, url=False,
                                                       error_message=False)
                return True

        # prepare order dictionary
        order_dict = {
            'partner_id': partner_id.id,
            'xtracta_document_id': document_id,
            'xtracta_document_url': document_url,
            'xtracta_configuration_id': self.id,
            'warehouse_id': self.warehouse_id.id,
            'company_id': self.warehouse_id and self.warehouse_id.company_id.id,
            'sale_order_source': 'xtracta',
            'analytic_account_id': self.analytic_account_id and self.analytic_account_id.id,
            'team_id': self.team_id and self.team_id.id
        }

        # check if order is available
        order_id = sale_order_obj.search([('xtracta_document_id', '=', document_id)])
        if order_id:
            sale_order_flag = False
            # 5 sep 2022 made this change to skip update process with order already in odoo
            # try:
            #     order_id.write(order_dict)
            # except Exception as error:
            #     error_msg = "[ERROR] SOME THING WRONG WITH UPDATE ORDER"
            #     self.create_xtracta_log_line_operation(msg=error_msg, status='success', log_id=log_id.id,
            #                                            request_data=False,
            #                                            response_data=False, process_data=order_data, url=False,
            #                                            error_message=error)
            # msg = "[UPDATE] SUCCESSFULLY UPDATE THE ORDER"
            # self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=log_id.id,
            #                                        request_data=False,
            #                                        response_data=False, process_data=order_data, url=False,
            #                                        error_message=False)
            # sale_order_flag = self.update_sale_order_line(order_id=order_id, order_line=order_line, log_id=log_id)
            # return True
        else:
            # create new sale order
            try:
                new_record = sale_order_obj.new(order_dict)
                new_record.onchange_partner_id()
                order_dict = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
                new_record = sale_order_obj.new(order_dict)
                new_record.with_context(with_company=self.warehouse_id.company_id.id).onchange_partner_shipping_id()
                order_dict = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
                order_id = sale_order_obj.create(order_dict)
            except Exception as error:
                error_msg = "[ERROR] SOME THING WRONG WITH CREATE ORDER"
                self.create_xtracta_log_line_operation(msg=error_msg, status='success', log_id=log_id.id,
                                                       request_data=False,
                                                       response_data=False, process_data=order_data, url=False,
                                                       error_message=error)
            #_logger.info("[ORDER] Successfully Create Order {}".format(order_id.name))
            msg = "{} SUCCESSFULLY CREATE ORDER".format(order_id.name)
            self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=log_id.id,
                                                   request_data=False,
                                                   response_data=False, process_data=order_data, url=False,
                                                   error_message=False)
            if order_id:
                # create sale order line using order order id
                sale_order_flag = self.create_sale_order_line(order_id=order_id, order_line=order_line, log_id=log_id)
        if sale_order_flag:
            if order_id.xtracta_order_status == 'not_archived':
                # print("archived")
                self.update_xtracta_document_status(document_id=document_id, xtracta_log_id=log_id, sale_order=order_id)
                order_id.update({'xtracta_order_status': 'archived'})
        return order_id

    def create_sale_order_line(self, order_id, order_line, log_id):
        """
        :param order_id: id of sale order
        :param order_line: dict of sale order line data
        :param log_id: log message object record id
        update the sale order line
        exist order lines wil update,  new will create
        """
        product_flag = True
        sale_order_line_obj = self.env['sale.order.line']
        product_obj = self.env['product.product']
        if not order_line:
            product_flag = False
            order_id.update({'order_has_error': True})
            return product_flag
        for line in order_line:
            product_code = line and line.get('Product Code')
            product_id = product_obj.search([('default_code', '=', product_code)], limit=1)
            if product_id:
                order_line_dict = {
                    'order_id': order_id.id,
                    'product_id': product_id.id,
                    'product_uom_qty': line.get('Quantity'),
                    'company_id': self.warehouse_id and self.warehouse_id.company_id.id
                }
                try:
                    new_order_line = sale_order_line_obj.new(order_line_dict)
                    new_order_line.product_id_change()
                    order_line = sale_order_line_obj._convert_to_write(
                        {name: new_order_line[name] for name in new_order_line._cache})
                    if product_id.taxes_id:
                        order_line.update({
                            'tax_id': [(6, 0, product_id.taxes_id.ids)]
                        })
                    sale_order_line_obj.create(order_line)
                except Exception as error:
                    error_msg = "[ERROR TO CREATE] SOME THING WRONG IN CREATE SALE ORDER LINE"
                    self.create_xtracta_log_line_operation(msg=error_msg, status='fail', log_id=log_id.id,
                                                           request_data=False,
                                                           response_data=False, process_data=line, url=False,
                                                           error_message=error)
                msg = "CREATE ORDER LINE IN {0} WITH {1}".format(order_id.name, product_id.name)
                self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=log_id.id,
                                                       request_data=False,
                                                       response_data=False, process_data=line, url=False,
                                                       error_message=False)
            else:
                product_flag = False
                msg = "[NOT FOUND] {} PRODUCT NOT FOUND ".format(line.get('Product Code'))
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=log_id.id,
                                                       request_data=False,
                                                       response_data=False, process_data=line, url=False,
                                                       error_message=False)
        if not product_flag:
            order_id.update({'order_has_error': True})
        return product_flag

    def update_sale_order_line(self, order_id, order_line, log_id):
        """
        :param order_id: id of sale order
        :param order_line: dict of sale order line data
        :param log_id: log message object record id
        update the sale order line
        exist order lines wil update,  new will create
        """
        sale_order_line_obj = self.env['sale.order.line'].search([('order_id', '=', order_id.id)])
        product_obj = self.env['product.product']
        product_flag = True
        if not order_line:
            product_flag = False
            order_id.update({'order_has_error': True})
            return product_flag
        for line in order_line:
            product_code = line and line.get('Product Code')
            product_id = product_obj.search([('default_code', '=', product_code)], limit=1)
            if product_id:
                order_line_id = sale_order_line_obj.filtered(lambda order_line: order_line.product_id == product_id)
                if order_line_id:
                    try:
                        order_line_id.write({
                            'product_id': product_id.id,
                            'product_uom_qty': line.get('Quantity'),
                            'tax_id': [(6, 0, self.tax_id.ids)]
                        })
                    except Exception as error:
                        error_message = "SOME ERROR TO UPDATE ORDER LINE"
                        self.create_xtracta_log_line_operation(msg=error_message, status='success', log_id=log_id.id,
                                                               request_data=False,
                                                               response_data=False, process_data=line, url=False,
                                                               error_message=error)
                    msg = "SUCCESSFULLY UPDATE ORDER LINE {0} IN {1}".format(product_id.name, order_id.name)
                    self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=log_id.id,
                                                           request_data=False,
                                                           response_data=False, process_data=line, url=False,
                                                           error_message=False)
                else:
                    msg = "CREATE NEW ORDER LINE IN {0} WITH {1}".format(order_id.name, product_id.name)
                    self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=log_id.id,
                                                           request_data=False,
                                                           response_data=False, process_data=line, url=False,
                                                           error_message=False)
            else:
                product_flag = False
                msg = "PRODUCT {0} NOT FOUND WHEN UPDATE THE ORDER LINE {1}".format(product_code, order_id.name)
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=log_id.id,
                                                       request_data=False,
                                                       response_data=False, process_data=line, url=False,
                                                       error_message=False)
        if not product_flag:
            order_id.update({'order_has_error': True})
        return product_flag

    def get_sale_order_val_by_doc_id(self, doc_id):
        """
        :param doc_id document id of order
        :return sale order dictionary
        """
        request_body = {
            'api_key': "{}".format(self.xtracta_api_key),
            'document_id': "{}".format(doc_id),
            'workflow_id': "{}".format(self.xtracta_workflow_id),
        }
        # create log operation
        xtracta_log_id = self.create_xtracta_log_operation(operation_name='get_order_data',
                                                           operation_type='import', ins_id=self.id,
                                                           document_no=doc_id, op_type='order')
        success_flag, api_url, response = XtractaRequest.send_request(service='get_document', request_body=request_body,
                                                                      configure_obj=self)
        if success_flag and isinstance(response, dict):
            status = response.get('documents_response') and response.get('documents_response').get('status')
            if status == '200':
                document = response.get('documents_response') and response.get('documents_response').get('document')
                msg = "GET DOCUMENT DATA USING DOCUMENT ID {}".format(doc_id)
                self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=xtracta_log_id.id,
                                                       request_data=request_body,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)
                if document:
                    order_dict = self.prepare_order_dict(document=document)
                    return xtracta_log_id, order_dict
            else:
                msg = "[NOT FOUND] DOCUMENT DATA NOT FOUND IN RESPONSE"
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                       request_data=request_body,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)
        else:
            msg = "[NOT FOUND] DOCUMENT DATA NOT FOUND IN RESPONSE"
            self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                   request_data=request_body,
                                                   response_data=response, process_data=False, url=api_url,
                                                   error_message=False)

    def prepare_order_dict(self, document):
        """
        :parameter document response
        :return dict well format order data
        """
        field_new_dict = {}
        order_line = []
        line_item_dict = {'order_line': order_line}
        field_data = document and document.get('field_data')
        for dict_value in field_data.get('field'):
            field_new_dict.update({dict_value.get('field_name'): dict_value.get('field_value')})
        field_set = field_data and field_data.get('field_set')
        if isinstance(field_set.get('row'), list):
            for row_value in field_set.get('row'):
                order_line.append(
                    {value.get('field_name'): value.get('field_value') for value in row_value.get('field')})
        elif isinstance(field_set.get('row'), dict):
            order_line.append(
                {value.get('field_name'): value.get('field_value') for value in field_set.get('row').get('field')})
        # remove old filed_data
        document.pop('field_data')
        # add new value in exist dict
        document.update(field_new_dict)
        document.update(line_item_dict)
        return document

    def update_xtracta_document_status(self, document_id, xtracta_log_id, sale_order):
        """
        :param xtracta_log_id: Xtracta operation log id
        :param document_id: Document id of xtracta
        update the xtracta document status
        """
        request_data = {
            'api_key': self.xtracta_api_key,
            'document_id': document_id,
            'api_download_status': 'archived'
        }
        success_flag, api_url, response = XtractaRequest.send_request(service='get_document', request_body=request_data,
                                                                      configure_obj=self)
        if success_flag:
            status = response and response.get('documents_response') and response.get('documents_response').get(
                'status')
            if status == '200':
                sale_order.update({'xtracta_order_status': 'archived'})
                msg = "{} DOCUMENT STATUS UPDATE".format(document_id)
                self.create_xtracta_log_line_operation(msg=msg, status='success', log_id=xtracta_log_id.id,
                                                       request_data=request_data,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)
            else:
                msg = "[ERROR] SOME WRONG WITH ORDER UPDATE {}".format(document_id)
                self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                       request_data=request_data,
                                                       response_data=response, process_data=False, url=api_url,
                                                       error_message=False)
        else:
            msg = "[ERROR] SOME WRONG WITH ORDER UPDATE {}".format(document_id)
            self.create_xtracta_log_line_operation(msg=msg, status='fail', log_id=xtracta_log_id.id,
                                                   request_data=request_data,
                                                   response_data=response, process_data=False, url=api_url,
                                                   error_message=False)

    # cron job necessary

    def export_customer_to_xtracta(self, obj_id):
        customers = self.env['res.partner'].search([('is_export_to_xtracta', '=', False)])
        xtracta_obj = self.search([('id', '=', obj_id)])
        if customers and xtracta_obj:
            customers = customers.filtered(lambda customers: customers.company_type == 'company')
            xtracta_log_id = self.create_xtracta_log_operation(operation_name=False,
                                                               operation_type='export', ins_id=xtracta_obj.id,
                                                               document_no=False, op_type='customer')
            customers.export_customer_xtracta(xtracta_obj=xtracta_obj, xtracta_log_id=xtracta_log_id)

    def export_product_to_xtracta(self, obj_id):
        product = self.env['product.product'].search([('is_export_to_xtracta', '=', False)])
        if product:
            xtracta_obj = self.search([('id', '=', obj_id)])
            xtracta_log_id = self.create_xtracta_log_operation(operation_name=False,
                                                               operation_type='export', ins_id=xtracta_obj.id,
                                                               document_no=False, op_type='product')
            product.export_product_xtracta(xtracta_obj, xtracta_log_id)

    def import_orders_cron_job(self, obj_id):
        xtracta_obj = self.search([('id', '=', obj_id)])
        if xtracta_obj:
            xtracta_obj.import_orders()

    @api.model
    def create(self, vals_list):
        res = super(XtractaDatabase, self).create(vals_list)
        cron_val = {
            'model_id': self.env.ref('xtracta_odoo_integration.model_xtracta_database').id,
            'state': 'code',
            'active': True,
            'user_id': self.env.ref('base.user_root').id,
            "numbercall": -1
        }
        if vals_list['xtracta_table_type'] == 'product':
            cron_val.update({
                'name': '[{}] EXPORT PRODUCT TO XTRACTA'.format(vals_list['name']),
                'code': 'model.export_product_to_xtracta({})'.format(res.id),
                "interval_number": 6,
                'interval_type': 'hours',
                "numbercall": -1
            })
        elif vals_list['xtracta_table_type'] == 'customer':
            cron_val.update({
                'name': '[{}] EXPORT CUSTOMER TO XTRACTA'.format(vals_list['name']),
                'code': 'model.export_customer_to_xtracta({})'.format(res.id),
                "interval_number": 6,
                'interval_type': 'hours',
                "numbercall": -1
            })
        elif vals_list['xtracta_table_type'] == 'order':
            cron_val.update({
                'name': '[{}] IMPORT ORDERS TO ODOO'.format(vals_list['name']),
                'code': 'model.import_orders_cron_job({})'.format(res.id),
                "interval_number": 30,
                'interval_type': 'minutes',
                "numbercall": -1
            })
        self.env['ir.cron'].create(cron_val)
        return res
