# Mimics addons/purchase/models/res_config_settings.py (real file, branch 18.0,
# verified against raw.githubusercontent.com/odoo/odoo/18.0/addons/purchase/models/res_config_settings.py
# on 2026-09-15). Trimmed to the fields checkbox's source index (P3) actually reads:
# po_order_approval is the flagship "is it standard?" example used throughout
# ARCHITECTURE.md and the seed cases (po-approval-threshold).
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    po_order_approval = fields.Boolean("Purchase Order Approval", default=lambda self: self.env.company.po_double_validation == 'two_step')
    po_double_validation_amount = fields.Monetary(related='company_id.po_double_validation_amount', string="Minimum Amount", currency_field='company_currency_id', readonly=False)
    use_po_lead = fields.Boolean(
        string="Security Lead Time for Purchase",
        config_parameter='purchase.use_po_lead',
        help="Margin of error for vendor lead times.")
    module_purchase_requisition = fields.Boolean("Purchase Agreements")
