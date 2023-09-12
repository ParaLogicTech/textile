import frappe


def execute():
	frappe.db.sql("""
		update `tabPrint Order`
		set fabric_warehouse = source_warehouse
	""")

	frappe.db.sql("""
		update `tabPretreatment Order`
		set fabric_warehouse = source_warehouse
	""")

	printing_settings = frappe.get_single("Fabric Printing Settings")
	printing_settings.default_printing_fabric_warehouse = printing_settings.default_printing_source_warehouse
	printing_settings.save()

	pretreatment_settings = frappe.get_single("Fabric Pretreatment Settings")
	pretreatment_settings.default_pretreatment_fabric_warehouse = pretreatment_settings.default_pretreatment_source_warehouse
	pretreatment_settings.save()
