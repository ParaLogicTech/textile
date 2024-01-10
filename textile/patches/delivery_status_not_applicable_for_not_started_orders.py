import frappe


def execute():
	frappe.db.sql("""
		update `tabPrint Order`
		set delivery_status = 'Not Applicable'
		where (status = 'Not Started' or docstatus = 0)
	""")

	frappe.db.sql("""
		update `tabPretreatment Order`
		set delivery_status = 'Not Applicable'
		where (status = 'Not Started' or docstatus = 0)
	""")
