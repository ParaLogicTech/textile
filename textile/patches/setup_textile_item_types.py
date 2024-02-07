import frappe
from textile.install import populate_textile_item_types


def execute():
	frappe.reload_doc("textile", "doctype", "textile_item_type")
	populate_textile_item_types()
