import frappe
from frappe.utils import cint


def get_item_details(args, out, doc=None, for_validate=False):
	item = frappe.get_cached_doc("Item", args.item_code)
	set_fabric_item_details(args, item, out)


def packing_slip_get_item_details(args, out):
	item = frappe.get_cached_doc("Item", args.item_code)
	set_fabric_item_details(args, item, out)


def stock_entry_get_item_details(args, out):
	item = frappe.get_cached_doc("Item", args.item_code)
	set_fabric_item_details(args, item, out)


def set_fabric_item_details(args, item, out):
	out.is_printed_fabric = cint(item.textile_item_type == "Printed Design")

	if item.textile_item_type in ("Greige Fabric", "Ready Fabric"):
		out.update({
			"fabric_item": item.name,
			"fabric_item_name": item.item_name,
		})
	else:
		out.update({
			"fabric_item": item.fabric_item or None,
			"fabric_item_name": item.fabric_item_name if item.fabric_item else "",
		})

	if args.get("print_order"):
		fabric_details = frappe.db.get_value("Print Order", args.print_order,
			("fabric_item", "fabric_item_name"), as_dict=1, cache=1) or {}
		out.update(fabric_details)


def get_price_list_rate(item_code, price_list, args):
	from textile.fabric_printing.doctype.print_pricing_rule.print_pricing_rule import get_printing_rate
	from textile.fabric_pretreatment.doctype.pretreatment_pricing_rule.pretreatment_pricing_rule import \
		get_pretreatment_rate
	from textile.controllers.textile_pricing_rule import get_fabric_rate

	if not item_code or not price_list or args.get("transaction_type") != "selling":
		return

	item = frappe.get_cached_doc("Item", item_code)
	customer = args.get("customer") or (args.get("quotation_to") == "Customer" and args.get("party_name"))

	if item.textile_item_type == "Printed Design":
		fabric_rate = get_fabric_rate(item.fabric_item, price_list, args)

		printing_rate = get_printing_rate(item_code, price_list, customer=customer,
			uom=args.get("uom"), conversion_factor=args.get("conversion_factor"))

		pretreatment_rate = 0
		include_pretreatment_price = frappe.db.get_value("Print Order", args.get("print_order"),
			"include_pretreatment_price", cache=1) if args.get("print_order") else False

		if include_pretreatment_price:
			pretreatment_rate = get_pretreatment_rate(item_code, price_list, customer=customer,
				uom=args.get("uom"), conversion_factor=args.get("conversion_factor"))

		return fabric_rate + printing_rate + pretreatment_rate

	elif item.textile_item_type == "Ready Fabric" and args.get("pretreatment_order"):
		fabric_rate = get_fabric_rate(item_code, price_list, args)

		pretreatment_rate = get_pretreatment_rate(item_code, price_list, customer=customer,
			uom=args.get("uom"), conversion_factor=args.get("conversion_factor"))

		return fabric_rate + pretreatment_rate
