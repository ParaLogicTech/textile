# import frappe
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


def override_sales_invoice_dashboard(data):
	from textile.utils import override_sales_transaction_dashboard
	return override_sales_transaction_dashboard(data)
