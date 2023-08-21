import frappe
from frappe import _
from frappe.utils import cint, flt


def validate_textile_item(item_code, textile_item_type, print_process_component=None):
	item = frappe.get_cached_doc("Item", item_code)

	if textile_item_type:
		if item.textile_item_type != textile_item_type:
			frappe.throw(_("{0} is not a {1} Item").format(frappe.bold(item_code), textile_item_type))

		if textile_item_type == "Process Component" and print_process_component:
			if item.print_process_component != print_process_component:
				frappe.throw(_("{0} is not a {1} Component Item").format(frappe.bold(item_code), print_process_component))

	from erpnext.stock.doctype.item.item import validate_end_of_life
	validate_end_of_life(item.name, item.end_of_life, item.disabled)


def gsm_to_grams(gsm, width_inch, length_meter=1):
	width_meter = flt(width_inch) * 0.0254
	return flt(gsm) * width_meter * flt(length_meter)


def is_row_return_fabric(doc, row):
	if row.get("print_order"):
		print_order_fabric = frappe.db.get_value("Print Order", row.print_order, "fabric_item", cache=1)
		return cint(row.item_code == print_order_fabric)
	elif row.item_code:
		item_details = frappe.get_cached_value("Item", row.item_code, ["textile_item_type", "is_customer_provided_item", "customer"], as_dict=1)
		return cint(
			item_details.textile_item_type in ("Greige Fabric", "Ready Fabric")
			and item_details.is_customer_provided_item
			and doc.customer == item_details.customer
		)
	else:
		return 0


@frappe.whitelist()
def get_fabric_item_details(fabric_item):
	out = frappe._dict()

	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()
	out.fabric_item_name = fabric_doc.item_name
	out.fabric_material = fabric_doc.fabric_material
	out.fabric_type = fabric_doc.fabric_type
	out.fabric_width = fabric_doc.fabric_width
	out.fabric_gsm = fabric_doc.fabric_gsm
	out.fabric_construction = fabric_doc.fabric_construction
	out.fabric_per_pickup = fabric_doc.fabric_per_pickup

	return out


@frappe.whitelist()
def get_rotated_image(file):
	from textile.rotated_image import get_rotated_image
	return get_rotated_image(file)
