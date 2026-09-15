# Mimics addons/stock/models/res_config_settings.py (real file, branch
# 18.0, verified against
# raw.githubusercontent.com/odoo/odoo/18.0/addons/stock/models/res_config_settings.py
# on 2026-09-15). Trimmed to the field the dropship seed case
# (docs/ARCHITECTURE.md §11.3) needs: module_stock_dropshipping, a
# module_* Boolean toggled from Settings -- structurally identical to
# purchase's po_order_approval, just installing a different addon.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_stock_dropshipping = fields.Boolean("Dropshipping")
