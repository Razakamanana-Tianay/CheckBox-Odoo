# Mimics addons/sale_margin/__manifest__.py (real file, branch 18.0,
# verified against
# raw.githubusercontent.com/odoo/odoo/18.0/addons/sale_margin/__manifest__.py
# on 2026-09-15). Full description kept (short) -- the so-line-margin seed
# case (docs/ARCHITECTURE.md §11.3) is a rung-5 "module" verdict, evidenced
# by the manifest alone (checkbox's source.py indexes manifests + settings
# fields, not model field bodies -- see that file's own module docstring).
{
    'name': 'Margins in Sales Orders',
    'version': '1.0',
    'category': 'Sales/Sales',
    'description': """
This module adds the 'Margin' on sales order.
=============================================

This gives the profitability by calculating the difference between the Unit
Price and Cost Price.
    """,
    'depends': ['sale_management'],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
