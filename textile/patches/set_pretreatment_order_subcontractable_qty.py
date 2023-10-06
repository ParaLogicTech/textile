import frappe


def execute():
	names = frappe.get_all("Pretreatment Order", {"docstatus": 1}, pluck="name")
	for name in names:
		doc = frappe.get_doc("Pretreatment Order", name)
		doc.set_production_packing_status(update=True, update_modified=False)
