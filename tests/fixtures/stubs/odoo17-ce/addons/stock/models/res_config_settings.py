# Mimics addons/stock/models/res_config_settings.py (real file, branch
# 17.0, verified against
# raw.githubusercontent.com/odoo/odoo/17.0/addons/stock/models/res_config_settings.py
# on 2026-09-15). Trimmed to the field the serial-tracking seed case
# (docs/ARCHITECTURE.md §11.3) needs: group_stock_production_lot ("Lots &
# Serial Numbers"), implied_group='stock.group_production_lot'.
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_stock_production_lot = fields.Boolean("Lots & Serial Numbers",
        implied_group='stock.group_production_lot', group="base.group_user,base.group_portal")
