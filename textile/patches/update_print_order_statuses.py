import frappe


def execute():
	print_orders = frappe.get_all("Print Order", pluck="name")
	for name in print_orders:
		doc = frappe.get_doc("Print Order", name)
		doc.set_sales_order_status(update=True, update_modified=False)
		doc.set_work_order_status(update=True, update_modified=False)
		doc.set_production_status(update=True, update_modified=False)
		doc.set_packing_status(update=True, update_modified=False)
		doc.set_delivery_status(update=True, update_modified=False)
		doc.set_billing_status(update=True, update_modified=False)
		doc.set_status(update=True, update_modified=False)

		doc.clear_cache()
