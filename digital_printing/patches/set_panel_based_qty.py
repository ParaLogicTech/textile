import frappe
from frappe.model.utils.rename_field import rename_field
from frappe.utils.fixtures import sync_fixtures


def execute():
	sync_fixtures(app="digital_printing")

	doctypes = ["Sales Order Item", "Delivery Note Item", "Sales Invoice Item"]

	for dt in doctypes:
		frappe.delete_doc_if_exists("Custom Field", f"{dt}-show_panel_in_print")

		if frappe.db.has_column(dt, 'show_panel_in_print'):
			rename_field(dt, "show_panel_in_print", "panel_based_qty")

	for name in frappe.get_all("Print Order", pluck="name"):
		doc = frappe.get_doc("Print Order", name)
		doc.calculate_totals()
		for d in doc.items:
			d.db_set("panel_based_qty", d.panel_based_qty, update_modified=False)
