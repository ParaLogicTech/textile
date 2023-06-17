import frappe


def execute():
	frappe.reload_doctype("Work Order")
	frappe.reload_doctype("Packing Slip Item")

	frappe.db.sql("""
		update `tabWork Order` wo
		inner join `tabPrint Order` pro on pro.name = wo.print_order
		set wo.packing_slip_required = pro.packing_slip_required
	""")

	frappe.db.sql("""
		update `tabPacking Slip Item` psi
		inner join `tabWork Order` wo on wo.sales_order_item = psi.sales_order_item
		set psi.work_order = wo.name
		where wo.packing_slip_required = 1
	""")
