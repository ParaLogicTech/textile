# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from textile.controllers.textile_pricing_rule import TextilePricingRule


class PretreatmentPricingRule(TextilePricingRule):
	doctype = "Pretreatment Pricing Rule"
	cache_field = "pretreatment_pricing_rule_names"

	@classmethod
	def get_customer_base_rate(cls, customer):
		return flt(frappe.get_cached_value("Customer", customer, "base_pretreatment_rate"))
	
	@classmethod
	def is_fixed_base_rate(cls, customer):
		return frappe.get_cached_value("Customer", customer, "is_fixed_pretreatment_rate")


@frappe.whitelist()
def get_pretreatment_rate(design_item, price_list, customer=None):
	return PretreatmentPricingRule.get_applied_rule(design_item, price_list, customer)["rule_rate"]


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
