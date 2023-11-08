import frappe


def execute():
	item_codes = frappe.get_all("Item", filters={
		"textile_item_type": ["in", ["Printed Design", "Ready Fabric", "Greige Fabric"]]
	}, pluck="name")

	for name in item_codes:
		doc = frappe.get_doc("Item", name)
		doc.set_fabric_conversion_uoms()
		doc.calculate_uom_conversion_factors()
		doc.update_child_table("uom_conversion_graph")
		doc.update_child_table("uoms")
