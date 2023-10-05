import frappe


def execute():
	frappe.db.sql("""
		update `tabItem`
		set is_sub_contracted_item = 1
		where textile_item_type = 'Ready Fabric'
	""")

	frappe.db.sql("""
		update `tabWork Order` wo
		inner join `tabSales Order` so on so.name = wo.sales_order
		set wo.expected_delivery_date = so.delivery_date
		where wo.expected_delivery_date is null
	""")
