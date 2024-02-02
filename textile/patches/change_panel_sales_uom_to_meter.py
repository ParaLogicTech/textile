import frappe


def execute():
	frappe.db.sql("""
		update `tabItem`
		set sales_uom = 'Meter'
		where sales_uom = 'Panel' and textile_item_type = 'Printed Design'
	""")
