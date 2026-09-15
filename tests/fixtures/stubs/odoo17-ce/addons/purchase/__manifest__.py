# Mimics addons/purchase/__manifest__.py (real file, branch 17.0,
# verified against raw.githubusercontent.com/odoo/odoo/17.0/addons/purchase/__manifest__.py
# on 2026-09-15). This is the seed case's flagship example (po-approval-threshold,
# §11.3): approval-above-a-threshold is a Purchase > Settings toggle, not code.
{
    'name': 'Purchase',
    'version': '1.2',
    'category': 'Inventory/Purchase',
    'summary': 'Purchase orders, tenders and agreements',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
