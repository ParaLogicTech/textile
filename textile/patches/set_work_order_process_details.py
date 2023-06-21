import frappe
from frappe.utils.fixtures import sync_fixtures


def execute():
	sync_fixtures(app="textile")
	frappe.db.sql("""
		update `tabWork Order` wo
		inner join `tabPrint Order` pro on pro.name = wo.print_order
		set
			wo.process_item = pro.process_item,
			wo.process_item_name = pro.process_item_name
	""")
