import frappe
from frappe.utils.fixtures import sync_fixtures
from frappe.model.utils.rename_field import rename_field

textile_item_type_dts = ["Item", "Item Group", "Item Source", "Brand"]


def execute():
	for dt in textile_item_type_dts:
		frappe.delete_doc_if_exists("Custom Field", f"{dt}-print_item_type")

	sync_fixtures(app="textile")

	for dt in textile_item_type_dts:
		rename_field(dt, "print_item_type", "textile_item_type")

	for dt in textile_item_type_dts:
		frappe.db.sql(f"""
			update `tab{dt}`
			set textile_item_type = 'Ready Fabric'
			where textile_item_type = 'Fabric'
		""")
