import frappe
# from frappe import _
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from textile.fabric_printing.doctype.print_order.print_order import validate_transaction_against_print_order
from textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order import validate_transaction_against_pretreatment_order
from textile.utils import is_row_return_fabric


class SalesInvoiceDP(SalesInvoice):
	def set_missing_values(self, for_validate=False):
		super().set_missing_values(for_validate=for_validate)
		self.set_is_return_fabric()

	def set_is_return_fabric(self):
		for d in self.items:
			d.is_return_fabric = is_row_return_fabric(self, d)

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc()
		validate_transaction_against_pretreatment_order(self)
		validate_transaction_against_print_order(self)

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		if self.update_stock:
			pretreatment_orders = set([d.pretreatment_order for d in self.items if d.get('pretreatment_order')])
			for name in pretreatment_orders:
				doc = frappe.get_doc("Pretreatment Order", name)
				doc.set_delivery_status(update=True)
				doc.validate_delivered_qty(from_doctype=self.doctype)
				doc.set_status(update=True)

				# Update packed qty for unpacked returns
				if self.is_return and self.reopen_order:
					doc.set_production_packing_status(update=True)

				doc.notify_update()

			print_orders = set([d.print_order for d in self.items if d.get('print_order')])
			print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]
			for name in print_orders:
				doc = frappe.get_doc("Print Order", name)
				doc.set_delivery_status(update=True)
				doc.validate_delivered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

				# Update packed qty for unpacked returns
				if self.is_return and self.reopen_order:
					doc.set_production_packing_status(update=True)

				doc.set_status(update=True)
				doc.notify_update()


def override_sales_invoice_dashboard(data):
	from textile.utils import override_sales_transaction_dashboard
	return override_sales_transaction_dashboard(data)
