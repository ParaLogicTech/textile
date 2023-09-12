import frappe


def execute():
	frappe.db.sql("""
		update `tabBOM Item` bom_i
		inner join `tabItem` item on item.name = bom_i.item_code
		set do_not_explode = 1
		where item.textile_item_type in ('Ready Fabric', 'Greige Fabric')
	""")
