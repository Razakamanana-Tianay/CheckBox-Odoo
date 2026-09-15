"""Fixture override of account.move._post -- the P4 seed case.

Mimics a real red-tier customization: overriding a posting method and using
sudo() and raw SQL while doing it. `checkbox classify` must return tier
'red' with reasons naming account.move._post, account.move.action_post, the
sudo() call and account_move's raw-SQL execute.
"""

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        result = super()._post(soft=soft)
        for move in self:
            move.sudo().write({"x_review_flagged": True})
        return result

    def action_post(self):
        result = super().action_post()
        self.env.cr.execute("UPDATE account_move SET x_touched = true WHERE id = %s", (self.id,))
        return result
