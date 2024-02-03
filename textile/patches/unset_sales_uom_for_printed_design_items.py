import frappe


def execute():
	frappe.db.sql("""
		update `tabItem`
		set sales_uom = null
		where textile_item_type = 'Printed Design'
	""")
