import frappe


def execute():
	frappe.db.sql("""
		update `tabDelivery Note Item` i
		set i.skip_sales_invoice = 1
		where i.is_return_fabric = 1 and i.billed_qty = 0
	""")

	dns = frappe.db.sql_list("""
		select distinct i.parent
		from `tabDelivery Note Item` i
		inner join `tabDelivery Note` p on p.name = i.parent
		where p.docstatus = 1 and i.is_return_fabric = 1 and i.billed_qty = 0
	""")

	for i, name in enumerate(dns):
		print(f"{i+1} / {len(dns)}: {name}")
		doc = frappe.get_doc("Delivery Note", name)
		doc.set_skip_sales_invoice_for_delivery_note(update=True, update_modified=False)
		doc.set_billing_status(update=True, update_modified=False)
		doc.set_status(update=True, update_modified=False)
