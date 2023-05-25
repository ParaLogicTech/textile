import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctypes = ["Sales Order", "Delivery Note", "Sales Invoice"]

	for dt in doctypes:
		frappe.reload_doctype(dt)
		frappe.delete_doc_if_exists("Custom Field", f"{dt}-show_panel_in_print")

		rename_field(dt, "show_panel_in_print", "panel_based_qty")
