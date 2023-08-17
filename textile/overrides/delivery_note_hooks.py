import frappe
from frappe import _
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from textile.digital_printing.doctype.print_order.print_order import check_print_order_is_closed
from textile.utils import is_row_return_fabric


class DeliveryNoteDP(DeliveryNote):
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
			doc.set_delivery_status(update=True)

			doc.validate_delivered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()

	def update_status(self, status):
		super().update_status(status)

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.run_method("update_status", None)


def map_print_order_reference_in_sales_invoice_item(mapper, target_doctype):
	if not mapper.get("Delivery Note Item"):
		return

	field_map = mapper["Delivery Note Item"]["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def override_delivery_note_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
