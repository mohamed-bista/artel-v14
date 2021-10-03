from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super(StockPickingInherit, self).button_validate()
        company_id = self.env['res.company'].sudo().search([('partner_id', '=', self.partner_id.id)], limit=1)
        company_transfer_id = self.env['stock.picking'].sudo().search([('origin', '=', self.sale_id.client_order_ref)],                                                              limit=1)
        if company_id.rule_type == 'sale_purchase' :
            intercompany_uid = company_id.intercompany_user_id and company_id.intercompany_user_id.id or False
            if not intercompany_uid:
                raise UserError(_('Provide at least one user for inter company relation for % ') % company.name)
            inter_user = self.env['res.users'].sudo().browse(intercompany_uid)
            lot_serial_data = []
            for line in self.move_line_ids.sudo():
                stock_prod_lot = self.env['stock.production.lot'].with_company(company_id.id).sudo().search([('product_id', '=', line.product_id.id), ('name', '=', line.lot_id.name), ('company_id', '=', company_id.id)])
                if not stock_prod_lot:
                    lot_serial_data += [line.prepare_lot_serial_data(company_id)]
            if len(lot_serial_data) > 0:
                lot_serial_number = self.env['stock.production.lot'].with_context(allowed_company_ids=inter_user.company_ids.ids).with_user(intercompany_uid).create(lot_serial_data)
                for move, line in zip (self.move_line_ids, company_transfer_id.move_line_ids_without_package) :
                    if move.product_id == line.product_id:
                        line_lot_id = self.env['stock.production.lot'].with_company(company_id.id).sudo().search([('product_id', '=', move.product_id.id), ('name', '=', move.lot_id.name), ('company_id', '=', company_id.id)])
                        line.lot_id = line_lot_id.id
        if self.origin == False:
            if self.picking_type_id.name == 'Delivery Orders' :
                sale_order_data = self._prepare_sale_order_data(self.partner_id, self.company_id)
                for line in self.move_line_ids.sudo():
                    sale_order_data['order_line'] += [(0, 0, self._prepare_sale_order_line_data(line, self.company_id))]
                    sale_order = self.env['sale.order'].create(sale_order_data)
                    self.origin = sale_order.name

        return res


    def _prepare_sale_order_data(self, partner, company):
        self.ensure_one()
        partner_addr = partner.sudo().address_get(['invoice', 'delivery', 'contact'])
        warehouse = company.warehouse_id and company.warehouse_id.company_id.id == company.id and company.warehouse_id or False
        if not warehouse:
            raise UserError(_('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies', company.name))
        return {
            'name': self.env['ir.sequence'].sudo().next_by_code('sale.order') or '/',
            'company_id': company.id,
            'team_id': self.env['crm.team'].with_context(allowed_company_ids=company.ids)._get_default_team_id(domain=[('company_id', '=', company.id)]).id,
            'warehouse_id': warehouse.id,
            'partner_id': partner.id,
            'pricelist_id': partner.property_product_pricelist.id,
            'partner_invoice_id': partner_addr['invoice'],
            'date_order': fields.Datetime.now(self),
            'fiscal_position_id': partner.property_account_position_id.id,
            'payment_term_id': partner.property_payment_term_id.id,
            'user_id': False,
            'auto_generated': True,
            'partner_shipping_id': partner_addr['delivery'],
            'picking_ids' : [(4, self.id)],
            'order_line': [],
        }

    @api.model
    def _prepare_sale_order_line_data(self, line, company):
        price = line.product_id.list_price
        taxes = line.product_id.taxes_id
        company_taxes = taxes.filtered(lambda t: t.company_id.id == company.id)
        quantity = line.product_uom_qty
        price = line.product_id.uom_id._compute_price(price, line.product_id.uom_id) or price
        return {
            'name': line.product_id.name,
            'product_uom_qty': quantity,
            'product_id': line.product_id.id or False,
            'product_uom': line.product_id.uom_id.id,
            'price_unit': price,
            'company_id': company.id,
        }

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def prepare_lot_serial_data(self, company_id):
        self.ensure_one()
        return {
            'name': self.lot_id.name,
            'company_id': company_id.id,
            'product_id': self.product_id.id,
            'create_date' : fields.Datetime.now(self)
        }
