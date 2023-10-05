from frappe import _


def update_purchase_order_from_work_order(purchase_order, row, work_order):
	row.pretreatment_order = work_order.get("pretreatment_order")


def update_purchase_order_mapper(mapper, target_doctype):
	if not mapper.get("Purchase Order Item"):
		return

	field_map = mapper["Purchase Order Item"]["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def update_purchase_receipt_mapper(mapper, target_doctype):
	if not mapper.get("Purchase Receipt Item"):
		return

	field_map = mapper["Purchase Receipt Item"]["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def override_purchase_order_dashboard(data):
	return override_purchase_transaction_dashboard(data, "Purchase Order")


def override_purchase_receipt_dashboard(data):
	return override_purchase_transaction_dashboard(data, "Purchase Receipt")


def override_purchase_invoice_dashboard(data):
	return override_purchase_transaction_dashboard(data, "Purchase Invoice")


def override_purchase_transaction_dashboard(data, doctype):
	data["internal_links"]["Pretreatment Order"] = ["items", "pretreatment_order"]
	data["internal_links"]["Print Order"] = ["items", "print_order"]

	textile_items = ["Pretreatment Order"]

	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")]
	if ref_section and doctype == "Purchase Invoice":
		ref_section = ref_section[0]
		ref_section["items"] = textile_items + ref_section["items"]
	else:
		data["transactions"].append({
			"label": _("Textile"),
			"items": textile_items
		})

	return data
