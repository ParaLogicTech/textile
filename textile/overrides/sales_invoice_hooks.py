import frappe
from frappe import _
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from textile.fabric_printing.doctype.print_order.print_order import validate_transaction_against_print_order
from textile.utils import is_row_return_fabric


class SalesInvoiceDP(SalesInvoice):
	def validate(self):
		super().validate()
		self.set_is_return_fabric()

	def set_is_return_fabric(self):
		for d in self.items:
			d.is_return_fabric = is_row_return_fabric(self, d)

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc()
		validate_transaction_against_print_order(self)


def override_sales_invoice_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
