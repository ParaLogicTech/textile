import frappe


def execute():
	frappe.db.sql("""
		update `tabItem`
		set is_sub_contracted_item = 0
	""")

	frappe.db.sql("""
		update `tabItem` im
		inner join `tabPurchase Order Item` poi on poi.item_code = im.name
		inner join `tabPurchase Order` po on po.name = poi.parent
		set im.is_sub_contracted_item = 1
		where po.docstatus = 1 and po.is_subcontracted = 1
	""")
