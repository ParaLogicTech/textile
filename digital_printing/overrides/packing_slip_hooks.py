import frappe
from frappe import _
from erpnext.stock.doctype.packing_slip.packing_slip import PackingSlip


class PackingSlipDP(PackingSlip):
	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_packed_status(update=True)

			doc.validate_packed_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()


def map_print_order_reference_in_delivery_note_item(item_mapper, source_doctype):
	if not item_mapper.get('field_map'):
		item_mapper['field_map'] = {}

	field_map = item_mapper["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def override_packing_slip_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Previous Documents")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
