from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super(StockPickingInherit, self).button_validate()
        company_id = self.env['res.company'].sudo().search([('partner_id', '=', self.partner_id.id)], limit=1)
        company_transfer_id = self.env['stock.picking'].sudo().search([('origin', '=', self.sale_id.client_order_ref)],
                                                                      limit=1)
        if company_id.rule_type == 'sale_purchase':
            intercompany_uid = company_id.intercompany_user_id and company_id.intercompany_user_id.id or False
            if not intercompany_uid:
                raise UserError(_('Provide at least one user for inter company relation for % ') % company.name)
            inter_user = self.env['res.users'].sudo().browse(intercompany_uid)
            lot_serial_data = []
            for line in self.move_line_ids.sudo():
                stock_prod_lot = self.env['stock.production.lot'].with_company(company_id.id).sudo().search(
                    [('product_id', '=', line.product_id.id), ('name', '=', line.lot_id.name),
                     ('company_id', '=', company_id.id)])
                if not stock_prod_lot:
                    lot_serial_data += [line.prepare_lot_serial_data(company_id)]
            if len(lot_serial_data) > 0:
                lot_serial_number = self.env['stock.production.lot'].with_context(
                    allowed_company_ids=inter_user.company_ids.ids).with_user(intercompany_uid).create(lot_serial_data)
                for move, line in zip(self.move_line_ids, company_transfer_id.move_line_ids_without_package):
                    if move.product_id == line.product_id:
                        line_lot_id = self.env['stock.production.lot'].with_company(company_id.id).sudo().search(
                            [('product_id', '=', move.product_id.id), ('name', '=', move.lot_id.name),
                             ('company_id', '=', company_id.id)])
                        line.lot_id = line_lot_id.id
        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def prepare_lot_serial_data(self, company_id):
        self.ensure_one()
        return {
            'name': self.lot_id.name,
            'company_id': company_id.id,
            'product_id': self.product_id.id,
            'create_date': fields.Datetime.now(self)
        }
