import frappe


def execute():
	if not frappe.db.has_column("Fabric Printer", "process_item"):
		return

	printers = frappe.get_all("Fabric Printer", pluck="name")
	for name in printers:
		process_item = frappe.db.get_value("Fabric Printer", name, "process_item")
		if not process_item:
			continue

		doc = frappe.get_doc("Fabric Printer", name)
		doc.append("process_items", {
			"process_item": process_item,
			"process_item_name": frappe.db.get_value("Item", process_item, "item_name"),
		})
		doc.update_child_table("process_items")
