import frappe


def execute():
	frappe.reload_doctype("Print Order")
	frappe.db.sql("""
		update `tabPrint Order`
		set status = 'Not Started'
		where status = 'To Confirm Order'
	""")
