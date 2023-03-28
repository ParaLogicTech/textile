import frappe
from frappe import _


def update_print_order_status(self, hook):
	if not (self.get('print_order') and self.get('print_order_item')):
		return

	doc = frappe.get_doc("Print Order", self.print_order)

	doc.set_work_order_status(update=True)
	doc.validate_work_order_qty(from_doctype=self.doctype, row_names=[self.print_order_item])

	doc.set_status(update=True)
	doc.notify_update()
