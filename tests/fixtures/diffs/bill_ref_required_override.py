"""Fixture override of account.move.action_post -- the P5 bill-ref-required
seed case.

Overriding a core business action is extension point #5 (docs/ARCHITECTURE.md
§4.3): "red by definition". `checkbox classify` must return tier 'red', with
a reason naming account.move.action_post -- confirmed a real method on both
17.0 and 18.0 CE (`.odoo-src/17.0/addons/account/models/account_move.py`).
"""

from odoo import models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        for move in self:
            if move.move_type == "in_invoice" and not move.ref:
                raise ValidationError(
                    "A vendor reference is required before posting a vendor bill."
                )
        return super().action_post()
