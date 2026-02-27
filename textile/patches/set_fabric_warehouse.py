import frappe


def execute():
	frappe.db.sql("""
		update `tabPrint Order`
		set fabric_warehouse = source_warehouse
	""")

	frappe.db.sql("""
		update `tabPretreatment Order`
		set fabric_warehouse = source_warehouse
	""")
