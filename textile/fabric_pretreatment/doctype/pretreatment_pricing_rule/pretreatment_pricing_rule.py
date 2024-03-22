# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from textile.controllers.textile_pricing_rule import TextilePricingRule
from erpnext.stock.doctype.item.item import convert_item_uom_for


class PretreatmentPricingRule(TextilePricingRule):
	doctype = "Pretreatment Pricing Rule"
	cache_field = "pretreatment_pricing_rule_names"


@frappe.whitelist()
def get_pretreatment_rate(design_item, price_list, customer=None, uom=None, conversion_factor=None):
	pretreatment_rate = PretreatmentPricingRule.get_applied_rule(design_item, price_list, customer)["rule_rate"]

	item = frappe.get_cached_doc("Item", design_item)
	if uom and uom != item.stock_uom:
		pretreatment_rate = convert_item_uom_for(
			value=pretreatment_rate,
			item_code=item.name,
			from_uom=item.stock_uom,
			to_uom=uom,
			conversion_factor=conversion_factor,
			is_rate=True
		)

	return pretreatment_rate


@frappe.whitelist()
def get_pretreatment_rate_breakup(item_code, price_list, customer=None):
	from textile.controllers.textile_pricing_rule import get_fabric_rate

	out = PretreatmentPricingRule.get_applied_rule(item_code, price_list, customer)
	fabric_rate = get_fabric_rate(item_code, price_list, frappe._dict({"customer": customer}))

	out.fabric_rate = fabric_rate
	out.price_list_rate = fabric_rate + flt(out.get("rule_rate"))

	out["applied_rules"] = []
	for d in [out.base_rate_rule] + out.addition_rules + out.multiplier_rules:
		if not d:
			continue

		out.applied_rules.append({
			"rule": d.name,
			"customer": d.customer,
			"type": d.type,
			"value": d.value,
		})

	return out
