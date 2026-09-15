"""Fixture new field on sale.order -- the P5 port-of-loading seed case.

A plain stored Char field via _inherit, no risky calls, no ir.rule/access
change. `checkbox classify` must return tier 'green' (default -- common.json
has no python rule that fires on a bare field declaration).
"""

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_port_of_loading = fields.Char(string="Port of Loading")
