import frappe
from frappe.utils.fixtures import sync_fixtures


def execute():
	frappe.reload_doctype("Sales Order Item")
	frappe.reload_doctype("Delivery Note Item")
	frappe.reload_doctype("Sales Invoice Item")
	frappe.reload_doctype("Packing Slip Item")

	sync_fixtures(app="textile")

	dts = ["Sales Order Item", "Delivery Note Item", "Sales Invoice Item", "Packing Slip Item", "Stock Entry Detail"]
	for dt in dts:
		frappe.db.sql(f"""
			update `tab{dt}` line
			inner join `tabItem` im on im.name = line.item_code
			set
				line.fabric_item = im.fabric_item,
				line.fabric_item_name = im.fabric_item_name
		""")

		frappe.db.sql(f"""
			update `tab{dt}` line
			inner join `tabItem` im on im.name = line.item_code
			set
				line.fabric_item = line.item_code,
				line.fabric_item_name = im.item_name
			where im.textile_item_type in ('Greige Fabric', 'Ready Fabric')
		""")

		if frappe.get_meta(dt).has_field("print_order"):
			frappe.db.sql(f"""
				update `tab{dt}` line
				inner join `tabPrint Order` pro on pro.name = line.print_order
				set
					line.fabric_item = pro.fabric_item,
					line.fabric_item_name = pro.fabric_item_name
			""")

		if frappe.get_meta(dt).has_field("is_printed_fabric"):
			frappe.db.sql(f"""
				update `tab{dt}` line
				inner join `tabItem` im on im.name = line.item_code
				set line.is_printed_fabric = 1
				where im.textile_item_type = 'Printed Design'
			""")
