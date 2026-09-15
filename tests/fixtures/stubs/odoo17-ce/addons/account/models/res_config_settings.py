# Mimics addons/account/models/res_config_settings.py (real file, branch
# 17.0, verified against
# raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/res_config_settings.py
# on 2026-09-15). Trimmed to the one field the tax-rounding-per-line seed
# case needs: the res.company field exposed on res.config.settings via
# related=. Note the real field has neither a positional label nor a
# help= kwarg -- checkbox's source.py indexer falls back to the field name
# itself in that case (see _settings_field_docs), which is exactly what
# happens here; this isn't a trimming artifact.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tax_calculation_rounding_method = fields.Selection(
        related='company_id.tax_calculation_rounding_method', string='Tax calculation rounding method', readonly=False)
