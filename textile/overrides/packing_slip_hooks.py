import frappe
from frappe import _
from frappe.utils import flt, round_down
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


def update_packing_slip_from_sales_order_mapper(mapper, target_doctype):
	def item_condition(source, source_parent, target_parent):
		if source.name in [d.sales_order_item for d in target_parent.get('items') if d.sales_order_item]:
			return False

		if source.delivered_by_supplier:
			return False

		if not source.is_stock_item:
			return False

		undelivered_qty, unpacked_qty = get_remaining_qty(source)
		return undelivered_qty > 0 and unpacked_qty > 0

	def update_item(source, target, source_parent, target_parent):
		if base_update_item:
			base_update_item(source, target, source_parent, target_parent)

		if source.get("print_order_item"):
			undelivered_qty, unpacked_qty = get_remaining_qty(source)
			target.qty = min(undelivered_qty, unpacked_qty)

	def get_remaining_qty(source):
		if source.get("print_order_item"):
			produced_qty = flt(frappe.db.get_value("Print Order Item", source.get("print_order_item"), "produced_qty", cache=1))
			produced_qty_order_uom = produced_qty / source.conversion_factor

			undelivered_qty = round_down(produced_qty_order_uom - flt(source.delivered_qty), source.precision("qty"))
			unpacked_qty = round_down(produced_qty_order_uom - flt(source.packed_qty), source.precision("qty"))
		else:
			undelivered_qty = flt(source.qty) - flt(source.delivered_qty)
			unpacked_qty = flt(source.qty) - flt(source.packed_qty)

		return undelivered_qty, unpacked_qty

	def postprocess(source, target):
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

		if print_orders and not target.package_type:
			target.package_type = frappe.db.get_single_value("Digital Printing Settings", "default_package_type_for_printed_fabrics")

		if base_postprocess:
			base_postprocess(source, target)

	base_postprocess = mapper.get("postprocess")
	mapper["postprocess"] = postprocess

	item_mapper = mapper.get("Sales Order Item")
	if item_mapper:
		base_update_item = item_mapper.get("postprocess")
		item_mapper["condition"] = item_condition
		item_mapper["postprocess"] = update_item


def override_packing_slip_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Previous Documents")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
