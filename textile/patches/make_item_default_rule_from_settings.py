import frappe
import erpnext
from frappe.utils.fixtures import sync_fixtures


def execute():
	global_default_fields = [
		"default_printing_fabric_warehouse",
		"default_printing_source_warehouse",
		"default_printing_wip_warehouse",
		"default_printing_fg_warehouse",
		"default_coating_fg_warehouse",
		"default_printing_cost_center",
		"default_coating_cost_center",
		"default_pretreatment_fabric_warehouse",
		"default_pretreatment_source_warehouse",
		"default_pretreatment_wip_warehouse",
		"default_pretreatment_fg_warehouse",
		"default_pretreatment_cost_center",
	]

	for fn in global_default_fields:
		frappe.db.set_default(fn, None)

	pretreatment_settings = frappe.get_single("Fabric Pretreatment Settings")
	printing_settings = frappe.get_single("Fabric Printing Settings")

	frappe.reload_doctype("Item Default Rule")
	sync_fixtures(app="textile")

	greige_defaults = frappe.new_doc("Item Default Rule")
	greige_defaults.textile_item_type = "Greige Fabric"
	greige_defaults.item_default_rule_name = greige_defaults.textile_item_type
	greige_defaults.company = erpnext.get_default_company()

	ready_defaults = frappe.new_doc("Item Default Rule")
	ready_defaults.textile_item_type = "Ready Fabric"
	ready_defaults.item_default_rule_name = ready_defaults.textile_item_type
	ready_defaults.company = erpnext.get_default_company()

	printed_defaults = frappe.new_doc("Item Default Rule")
	printed_defaults.textile_item_type = "Printed Design"
	printed_defaults.item_default_rule_name = printed_defaults.textile_item_type
	printed_defaults.company = erpnext.get_default_company()

	greige_defaults.default_warehouse = pretreatment_settings.default_pretreatment_fabric_warehouse
	greige_defaults.default_rejected_warehouse = pretreatment_settings.default_pretreatment_rejected_warehouse
	greige_defaults.selling_cost_center = pretreatment_settings.default_pretreatment_cost_center
	greige_defaults.buying_cost_center = pretreatment_settings.default_pretreatment_cost_center

	ready_defaults.default_warehouse = printing_settings.default_printing_fabric_warehouse
	ready_defaults.default_rejected_warehouse = pretreatment_settings.default_pretreatment_rejected_warehouse
	ready_defaults.default_rm_warehouse = pretreatment_settings.default_pretreatment_source_warehouse
	ready_defaults.default_wip_warehouse = pretreatment_settings.default_pretreatment_wip_warehouse
	ready_defaults.default_coating_fg_warehouse = printing_settings.default_coating_fg_warehouse
	ready_defaults.selling_cost_center = pretreatment_settings.default_pretreatment_cost_center
	ready_defaults.buying_cost_center = pretreatment_settings.default_pretreatment_cost_center

	printed_defaults.default_warehouse = printing_settings.default_printing_fg_warehouse
	printed_defaults.default_rejected_warehouse = printing_settings.default_printing_rejected_warehouse
	printed_defaults.default_rm_warehouse = printing_settings.default_printing_source_warehouse
	printed_defaults.default_wip_warehouse = printing_settings.default_printing_wip_warehouse
	printed_defaults.selling_cost_center = printing_settings.default_printing_cost_center
	printed_defaults.buying_cost_center = printing_settings.default_printing_cost_center
	printed_defaults.packing_slip_required = "Yes"
	printed_defaults.produce_fg_in_wip_warehouse = "Yes"

	greige_defaults.save()
	ready_defaults.save()
	printed_defaults.save()
