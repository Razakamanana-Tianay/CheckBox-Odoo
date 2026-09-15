# Mimics addons/account/models/company.py (real file, branch 17.0, verified
# against raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/company.py
# on 2026-09-15). Trimmed to the field the tax-rounding-per-line seed case
# (docs/ARCHITECTURE.md §11.3) needs: tax_calculation_rounding_method lives
# on res.company, default 'round_per_line'.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    tax_calculation_rounding_method = fields.Selection([
        ('round_per_line', 'Round per Line'),
        ('round_globally', 'Round Globally'),
        ], default='round_per_line', string='Tax Calculation Rounding Method')
