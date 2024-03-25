import frappe
from frappe.utils import flt, cint
from frappe.model.document import Document


class TextilePricingRule(Document):
	doctype = ""
	cache_field = ""

	match_fields = ['price_list', 'customer_group', 'fabric_material', 'fabric_type']
	range_fields = ['fabric_width', 'fabric_gsm']

	filter_fields = (
		match_fields
		+ [f"{f}_lower_limit" for f in range_fields]
		+ [f"{f}_upper_limit" for f in range_fields]
	)

	def validate(self):
		if self.type == "Add/Subtract":
			self.validate_value("value", "!=", 0, raise_exception=True)
		else:
			self.validate_value("value", ">", 0, raise_exception=True)

	def on_change(self):
		self.clear_pricing_rule_cache()

	def after_rename(self, old_name, new_name, merge):
		self.clear_pricing_rule_cache()

	@classmethod
	def clear_pricing_rule_cache(cls):
		frappe.cache().delete_value(cls.cache_field)

	@classmethod
	def get_applied_rule(cls, item_code, price_list, customer=None):
		filters = cls.get_filters_dict(item_code, price_list, customer)
		applicable_rules = cls.get_applicable_rules_for_filters(filters)

		base_rate_rule = cls.get_base_rate_rule(applicable_rules, customer)

		base_rate = flt(base_rate_rule.value) if base_rate_rule else 0
		rate = base_rate

		additions = []
		multipliers = []

		if not cls.is_fixed_base_rate(customer):
			for rule in applicable_rules:
				if rule.type == "Add/Subtract":
					rate += flt(rule.value)
					additions.append(rule)

			for rule in applicable_rules:
				if rule.type == "Multiply":
					rate *= flt(rule.value)
					multipliers.append(rule)

		return frappe._dict({
			"rule_rate": rate,
			"base_rate": base_rate,
			"base_rate_rule": base_rate_rule,
			"addition_rules": additions,
			"multiplier_rules": multipliers,
		})

	@classmethod
	def get_applicable_rules_for_filters(cls, filters):
		if not filters:
			filters = frappe._dict()

		rules = cls.get_rule_docs()

		applicable_rules = []
		for rule in rules:
			rule_dict = rule.get_applicable_rule_dict(filters)
			if rule_dict:
				applicable_rules.append(rule_dict)

		return applicable_rules

	def get_applicable_rule_dict(self, filters):
		match_filters = self.get_match_filters()
		range_filters = self.get_range_filters()

		if not match_filters and not range_filters:
			# global rule, applicable to all
			required_filters_matched = True
		else:
			required_filters_matched = True

			if match_filters:
				for field, required_value in match_filters.items():
					if field == "customer_group":
						if not self.match_tree("Customer Group", required_value, filters.get(field)):
							required_filters_matched = False
							break
					elif filters.get(field) != required_value:
						required_filters_matched = False
						break

			if range_filters:
				for field, conditions in range_filters.items():
					for operator, val2 in conditions:
						if not frappe.compare(flt(filters.get(field)), operator, val2):
							required_filters_matched = False
							break

		if required_filters_matched:
			return self.get_rule_match_dict(match_filters)
		else:
			return None

	@staticmethod
	def match_tree(doctype, required, actual):
		meta = frappe.get_meta(doctype)
		parent_field = meta.nsm_parent_field

		actual_ancestors = []
		if actual:
			current_name = actual
			while current_name:
				current_doc = frappe.get_cached_doc(doctype, current_name)
				actual_ancestors.append(current_doc.name)
				current_name = current_doc.get(parent_field)

		return required in actual_ancestors

	def get_match_filters(self):
		required_filters = frappe._dict()
		for f in self.match_fields:
			if self.get(f):
				required_filters[f] = self.get(f)

		return required_filters

	def get_range_filters(self):
		required_filters = frappe._dict()
		for f in self.range_fields:
			lower_limit_field = f"{f}_lower_limit"
			upper_limit_field = f"{f}_upper_limit"

			if self.get(lower_limit_field):
				required_filters.setdefault(f, []).append((">=", flt(self.get(lower_limit_field))))
			if self.get(upper_limit_field):
				required_filters.setdefault(f, []).append(("<=", flt(self.get(upper_limit_field))))

		return required_filters

	def get_rule_match_dict(self, match_filters):
		rule_dict = frappe._dict({
			"name": self.name,
			"type": self.type,
			"value": flt(self.value),
			"required_filters": match_filters,
		})

		if self.get('customer_group'):
			rule_dict['customer_group_lft'] = frappe.get_cached_value("Customer Group", self.get('customer_group'), 'lft')

		return rule_dict

	@classmethod
	def get_filters_dict(cls, item_code, price_list, customer):
		if not customer:
			customer = {}

		if isinstance(item_code, str):
			item_code = frappe.get_cached_doc("Item", item_code)
		if customer and isinstance(customer, str):
			customer = frappe.get_cached_doc("Customer", customer)

		filters = frappe._dict()

		for f in cls.match_fields + cls.range_fields:
			if customer.get(f) and f in ("customer_group",):
				filters[f] = customer.get(f)
			if item_code.get(f):
				filters[f] = item_code.get(f)

		filters["price_list"] = price_list

		return filters

	@classmethod
	def get_base_rate_rule(cls, applicable_rules, customer):
		def sorting_function(d):
			no_of_matches = len(d.required_filters)

			filter_precedences = []
			for k in d.required_filters:
				if k in filter_sort:
					index = filter_sort.index(k)

					if k == 'customer_group':
						filter_precedences.append((index, -cint(d.customer_group_lft)))
					else:
						filter_precedences.append((index,))
				else:
					filter_precedences.append(999999)

			filter_precedences = sorted(filter_precedences)

			return tuple([-no_of_matches] + filter_precedences)

		base_rate_rule = None

		if customer:
			customer_base_rate = cls.get_customer_base_rate(customer)
			if customer_base_rate:
				base_rate_rule = frappe._dict({
					"value": customer_base_rate,
					"type": "Base Rate",
					"required_filters": {
						"customer": customer
					}
				})

		if not base_rate_rule:
			filter_sort = ['price_list', 'customer_group', 'fabric_material', 'fabric_type']
			base_rates = [rule for rule in applicable_rules if rule.type == "Base Rate"]
			base_rates = sorted(base_rates, key=lambda d: sorting_function(d))
			if base_rates:
				base_rate_rule = base_rates[0]

		return base_rate_rule

	@classmethod
	def get_customer_base_rate(cls, customer):
		return None

	@classmethod
	def get_rule_docs(cls):
		names = cls.get_rule_names()
		docs = [frappe.get_cached_doc(cls.doctype, name) for name in names]
		return docs

	@classmethod
	def get_rule_names(cls):
		def generator():
			names = [d.name for d in frappe.get_all(cls.doctype)]
			return names

		return frappe.cache().get_value(cls.cache_field, generator)


def get_fabric_rate(fabric_item_code, price_list, args=None):
	from erpnext.stock.get_item_details import get_price_list_rate_for

	if not args:
		args = frappe._dict()

	is_customer_provided_item = frappe.get_cached_value("Item", fabric_item_code, "is_customer_provided_item")
	if is_customer_provided_item:
		fabric_rate = 0
	else:
		fabric_rate = flt(get_price_list_rate_for(fabric_item_code, price_list, args))

	return fabric_rate
