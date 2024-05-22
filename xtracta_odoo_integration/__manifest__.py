# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    # App information
    'name': 'Xtracta Odoo Integration',
    'category': 'Website',
    'version': '14.07.4.2021',
    'summary': '',
    'license': 'OPL-1',

    # Dependencies

    'depends': ['sale', 'stock' ],

    # Views

    'data': [
        'security/ir.model.access.csv',
        'data/ir_crone.xml',
        'views/xtracta_database.xml',
        'views/xtracta_columns.xml',
        'views/xtracta_log.xml',
        'views/product_product.xml',
        'views/res_partner.xml',
        'views/sale.xml',
        'views/account_move.xml',
    ],

    # Odoo Store Specific

    'images': [],

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'live_test_url': '',
}
# 14.27.12.2021
# Initial version of the app
# Develop by shyam7636

# 14.31.12.2021
# change module image
# customer search by customer code
# concat product name with variant name

# 14.01.2.2021
# add tax when create sale order line

# 14.03.2.2021
# filter fetch ony customer which type is only company

# 14.10.2.2021
# update customer and product from odoo
# 14.1.10.2.2021 fix the singleton error

# 14.2.10.2.2021
# order continue if it have any error


# 14.0.07.3.2021
# export company code in billing and shipping address

# 14.15.3.2021
# fix iteration bug
# change dependency
# 14.23.3.2021
# add two accounting field in odoo

# 14.24.3.2021
# move xtracta field to xtracta page

# 14.07.4.2021
# add xtracta_account_expense_categ_id
