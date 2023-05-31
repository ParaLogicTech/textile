import frappe
from frappe import _
from erpnext.stock.doctype.packing_slip.packing_slip import PackingSlip
from textile.overrides.taxes_and_totals_hooks import calculate_panel_qty


class PackingSlipDP(PackingSlip):
	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_packing_status(update=True)

			doc.validate_packed_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()

	def calculate_totals(self):
		super().calculate_totals()
		calculate_panel_qty(self)


def map_print_order_reference_in_delivery_note_item(item_mapper, source_doctype):
	if not item_mapper.get('field_map'):
		item_mapper['field_map'] = {}

	field_map = item_mapper["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def update_sales_order_to_print_order_mapper(mapper, target_doctype):
	def postprocess(source, target):
		if base_postprocess:
			base_postprocess(source, target)

		print_orders = [d.get("print_order") for d in source.get("items") if d.get("print_order")]
		print_orders = list(set(print_orders))

		for name in print_orders:
			print_order_details = frappe.db.get_value("Print Order", name,
				["fabric_item", "fabric_item_name", "default_length_uom", "wip_warehouse"], as_dict=1)

			target.append('items', {
				"item_code": print_order_details.fabric_item,
				"item_name": "{0} ({1})".format(print_order_details.fabric_item_name, _("Return Fabric")),
				"qty": 0,
				"uom": print_order_details.default_length_uom,
				"source_warehouse": print_order_details.wip_warehouse,
				"print_order": name,
			})

	def update_item(source, target, source_parent, target_parent):
		if base_update_item:
			base_update_item(source, target, source_parent, target_parent)

		if source.get("print_order_item"):
			produced_qty = frappe.db.get_value("Print Order Item", source.get("print_order_item"), "produced_qty", cache=1)
			target.qty = min(target.qty, produced_qty)

	base_postprocess = mapper.get("postprocess")
	mapper["postprocess"] = postprocess

	item_mapper = mapper.get("Sales Order Item")
	if item_mapper:
		base_update_item = item_mapper.get("postprocess")
		item_mapper["postprocess"] = update_item


def override_packing_slip_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Previous Documents")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
