# Mimics addons/stock/models/stock_picking.py (real file, branch 18.0,
# verified against
# raw.githubusercontent.com/odoo/odoo/18.0/addons/stock/models/stock_picking.py
# on 2026-09-15). Trimmed to the class/method signature the
# quality-check-ce seed case (docs/ARCHITECTURE.md §11.3) needs a real
# extension-point target for: button_validate() on stock.picking,
# extension point #5 (§4.3 -- overriding a core action, red by
# definition). Body trimmed to its first real statements; the full method
# runs ~40 lines in real source and none of the rest changes what a
# ladder-walking agent needs to see to pick this as the extension point.
from odoo import models
from odoo.tools import float_is_zero


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'barcodes.barcode_events_mixin']

    def button_validate(self):
        self = self.filtered(lambda p: p.state != 'done')
        draft_picking = self.filtered(lambda p: p.state == 'draft')
        draft_picking.action_confirm()
        for move in draft_picking.move_ids:
            if float_is_zero(move.quantity, precision_rounding=move.product_uom.rounding) and \
               not float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                move.quantity = move.product_uom_qty
        if not self.env.context.get('skip_sanity_check', False):
            self._sanity_check()
