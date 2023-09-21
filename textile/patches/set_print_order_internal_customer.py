import frappe


def execute():
	internal_customers = frappe.get_all("Customer", {"is_internal_customer": 1}, pluck="name")
	if not internal_customers:
		return

	print_orders = frappe.get_all("Print Order", {"customer": ["in", internal_customers]}, pluck="name")
	for name in print_orders:
		doc = frappe.get_doc("Print Order", name)
		print(f"Updating Print Order {name} (Customer {doc.customer}) Internal Customer")
		doc.validate_is_internal_customer()
		doc.db_set({
			"is_internal_customer": doc.is_internal_customer,
			"is_fabric_provided_by_customer": doc.is_fabric_provided_by_customer,
		}, update_modified=False)
