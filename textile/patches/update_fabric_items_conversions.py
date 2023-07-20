import frappe


def execute():
	item_codes = frappe.get_all("Item", filters={
		"textile_item_type": ["in", ["Fabric", "Ready Fabric", "Greige Fabric", "Printed Design"]]
	}, pluck="name")

	for item_code in item_codes:
		doc = frappe.get_doc("Item", item_code)
		doc.run_method("validate_fabric_uoms")
		doc.calculate_uom_conversion_factors()
		doc.db_update()

		doc.update_child_table("uoms")
		doc.update_child_table("uom_conversion_graph")
