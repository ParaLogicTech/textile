import frappe
from frappe import _
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from textile.fabric_printing.doctype.print_order.print_order import check_print_order_is_closed
from textile.utils import is_row_return_fabric


class SalesInvoiceDP(SalesInvoice):
	def validate(self):
		super().validate()
		check_print_order_is_closed(self)
		self.set_is_return_fabric()

	def set_is_return_fabric(self):
		for d in self.items:
			d.is_return_fabric = is_row_return_fabric(self, d)

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_billing_status(update=True)

			doc.validate_billed_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()


def override_sales_invoice_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
