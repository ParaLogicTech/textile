import frappe
from frappe.utils.fixtures import sync_fixtures


def execute():
	sync_fixtures(app="textile")
	frappe.db.sql("""
		update `tabWork Order` wo
		inner join `tabPrint Order` pro on pro.name = wo.print_order
		set
			wo.fabric_item = pro.fabric_item,
			wo.fabric_item_name = pro.fabric_item_name,
			wo.fabric_material = pro.fabric_material,
			wo.fabric_width = pro.fabric_width,
			wo.fabric_gsm = pro.fabric_gsm
	""")
