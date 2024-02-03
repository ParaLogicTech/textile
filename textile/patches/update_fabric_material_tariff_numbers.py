import frappe
from textile.install import populate_customs_tariff_number, populate_fabric_material
from textile.textile.doctype.fabric_material.fabric_material import update_item_tariff_numbers


def execute():
	frappe.reload_doc("textile", "doctype", "fabric_tariff_number")
	frappe.reload_doc("textile", "doctype", "fabric_material")

	populate_customs_tariff_number()
	populate_fabric_material(overwrite=True)

	for fabric_material in frappe.get_all("Fabric Material", pluck="name"):
		update_item_tariff_numbers(fabric_material)
