from odoo import api, fields, models


class XtractaSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        res = super(XtractaSaleOrderLine, self)._prepare_invoice_line(**optional_values)
        if res.get('product_id'):
            product_id = self.env['product.product'].browse(res.get('product_id'))
            if product_id and (
                    product_id.type == 'product') and self.order_id and self.order_id.xtracta_configuration_id:
                res.update({
                    'account_id': self.order_id.xtracta_configuration_id.xtracta_account_income_categ_id and self.order_id.xtracta_configuration_id.xtracta_account_income_categ_id.id or False})
        return res
