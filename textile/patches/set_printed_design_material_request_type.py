import frappe


def execute():
	frappe.db.sql("""
		update `tabItem`
		set default_material_request_type = 'Manufacture'
		where textile_item_type = 'Printed Design'
	""")
