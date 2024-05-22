# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError
from .xtracta_request import XtractaRequest


class XtractaSaleOrder(models.Model):
    _inherit = 'sale.order'

    xtracta_document_id = fields.Char(string='Xtracta Document Id', copy=False)
    xtracta_document_url = fields.Char(string='Xtracta Document URL', copy=False)
    xtracta_configuration_id = fields.Many2one('xtracta.database', string='Xtracta Configuration', copy=False)
    xtracta_order_status = fields.Selection([('archived', 'Archived'), ('not_archived', 'Not Archived')],
                                            string='Xtracta Order Status', default='not_archived',
                                            copy=False, required=1)
    order_has_error = fields.Boolean(string="Order Has Error ?", copy=False)

    def xtracta_archive_order(self):
        """
        update the status of document
        """
        xtracta_obj = self.env['xtracta.database'].search([('xtracta_default_obj', '=', True)], limit=1)
        if not xtracta_obj:
            raise ValidationError(_('Please Select Any Order Instance As Default'))

        request_data = {
            'api_key': xtracta_obj.xtracta_api_key,
            'document_id': '{}'.format(self.xtracta_document_id),
            'api_download_status': 'archived'
        }
        try:
            success_flag, api_url, response = XtractaRequest.send_request(service='update_document',
                                                                          request_body=request_data,
                                                                          configure_obj=xtracta_obj)
        except Exception as error:
            raise ValidationError(_(error))
        if success_flag:
            status = response and response.get('documents_response') and response.get('documents_response').get(
                'status')
            if status == '200':
                self.update({'xtracta_order_status': 'archived'})
            else:
                raise ValidationError(_("Something Wrong In Document Status Update \n {}".format(request_data)))
        else:
            raise ValidationError(_("Something Wrong In Document Status Update \n {}".format(request_data)))

    def _prepare_invoice(self):
        res = super(XtractaSaleOrder, self)._prepare_invoice()
        if self.xtracta_configuration_id:
            res.update({'xtracta_instance_id':self.xtracta_configuration_id and self.xtracta_configuration_id.id})
        return res