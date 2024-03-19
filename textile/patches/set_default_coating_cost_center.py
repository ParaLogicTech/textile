import frappe


def execute():
	doc = frappe.get_single("Fabric Printing Settings")
	doc.default_coating_cost_center = doc.default_printing_cost_center
	doc.save(ignore_permissions=True)

