import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder


class SalesOrderDP(SalesOrder):
	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_ordered_status(update=True)

			doc.validate_ordered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()


def override_sales_invoice_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(1, "Print Order")
	return data
