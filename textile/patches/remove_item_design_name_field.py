import frappe


def execute():
	transaction_dts = [
		"Sales Order Item", "Delivery Note Item", "Sales Invoice Item", "Packing Slip Item",
		"BOM Item", "Stock Entry Detail"
	]

	frappe.delete_doc_if_exists("Custom Field", "Item-design_name")

	frappe.db.sql("""
		update `tabItem`
		set item_name = design_name
		where ifnull(design_name, '') != '' and textile_item_type = 'Printed Design'
	""")

	for dt in transaction_dts:
		frappe.db.sql(f"""
			update `tab{dt}` t
			inner join `tabItem` i on i.name = t.item_code
			set t.item_name = i.item_name
			where i.textile_item_type = 'Printed Design'
		""")

	frappe.db.sql("""
		update `tabWork Order` t
		inner join `tabItem` i on i.name = t.production_item
		set t.item_name = i.item_name
		where i.textile_item_type = 'Printed Design'
	""")

	frappe.db.sql("""
		update `tabBOM` t
		inner join `tabItem` i on i.name = t.item
		set t.item_name = i.item_name
		where i.textile_item_type = 'Printed Design'
	""")
