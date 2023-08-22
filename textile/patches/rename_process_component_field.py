import frappe
from frappe.utils.fixtures import sync_fixtures
from frappe.model.utils.rename_field import rename_field


def execute():
	frappe.delete_doc_if_exists("Custom Field", f"Item-print_process_component")

	sync_fixtures(app="textile")

	rename_field("Item", "print_process_component", "process_component")
