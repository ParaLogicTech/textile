# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from textile.utils import validate_textile_item, pretreatment_components

filter_fields = ['fabric_material', 'fabric_type']


class PretreatmentProcessRule(Document):
	def validate(self):
		self.validate_duplicate()
		self.validate_process_items()

	def on_change(self):
		clear_pretreatment_process_rule_cache()

	def after_rename(self, old_name, new_name, merge):
		clear_pretreatment_process_rule_cache()

	def validate_process_items(self):
		all_empty = True

		for component_item_field, component_type in pretreatment_components.items():
			if self.get(f"{component_item_field}_unset"):
				self.set(component_item_field, None)

			if self.get(component_item_field):
				validate_textile_item(self.get(component_item_field), "Process Component", component_type)
				all_empty = False
			else:
				self.set(f"{component_item_field}_name", None)

		if all_empty:
			frappe.throw(_("Please select at least one process component"))

	def validate_duplicate(self):
		filters = {}

		if not self.is_new():
			filters['name'] = ['!=', self.name]

		for f in filter_fields:
			if self.get(f):
				filters[f] = self.get(f)
			else:
				filters[f] = ['is', 'not set']

		existing = frappe.get_all("Pretreatment Process Rule", filters=filters)
		if existing:
			frappe.throw(_("{0} already exists with the same filters")
				.format(frappe.get_desk_link("Pretreatment Process Rule", existing[0].name)))

	def get_applicable_rule_dict(self, filters):
		required_filters = self.get_required_filters()

		if required_filters:
			# check if required filters matches
			required_filters_matched = True
			for field, required_value in required_filters.items():
				if filters.get(field) != required_value:
					required_filters_matched = False
					break
		else:
			# global rule, applicable to all
			required_filters_matched = True

		if required_filters_matched:
			return self.get_rule_match_dict(required_filters)
		else:
			return None

	def get_required_filters(self):
		required_filters = frappe._dict()
		for f in filter_fields:
			if self.get(f):
				required_filters[f] = self.get(f)

		return required_filters

	def get_rule_match_dict(self, required_filters):
		rule_dict = self.as_dict()
		rule_dict.required_filters = required_filters

		return rule_dict


def get_pretreatment_process_values(fabric_item):
	filters = get_filters_dict(fabric_item)
	applicable_rules = get_applicable_rules_for_filters(filters)
	return get_default_values_dict(applicable_rules)


def get_default_values_for_filters(filters):
	applicable_rules = get_applicable_rules_for_filters(filters)
	return get_default_values_dict(applicable_rules)


def get_default_values_dict(applicable_rules, filter_sort=None):
	def sorting_function(d):
		no_of_matches = len(d.required_filters)

		filter_precedences = []
		for k in d.required_filters:
			if k in filter_sort:
				index = filter_sort.index(k)
				filter_precedences.append((index,))
			else:
				filter_precedences.append(999999)

		filter_precedences = sorted(filter_precedences)

		return tuple([-no_of_matches] + filter_precedences)

	# sort: more matches first, precendent filters first
	if not filter_sort:
		filter_sort = ['fabric_material', 'fabric_type']

	applicable_rules = sorted(applicable_rules, key=lambda d: sorting_function(d))

	rule_meta = frappe.get_meta("Pretreatment Process Rule")
	values = frappe._dict()
	for rule in applicable_rules:
		for fieldname, value in rule.items():
			if fieldname == "pretreatment_process_rule_name":
				continue

			if value and fieldname not in filter_fields and rule_meta.has_field(fieldname):
				if not values.get(fieldname):
					values[fieldname] = value

	for component_item_field in pretreatment_components:
		if values.get(f"{component_item_field}_unset"):
			values[component_item_field] = None

	return values


def get_filters_dict(fabric_item):
	if not fabric_item:
		fabric_item = {}

	if isinstance(fabric_item, str):
		fabric_item = frappe.get_cached_doc("Item", fabric_item)

	filters = frappe._dict()
	for f in filter_fields:
		if fabric_item.get(f):
			filters[f] = fabric_item.get(f)

	return filters


def get_applicable_rules_for_filters(filters):
	if not filters:
		filters = frappe._dict()

	rules = get_pretreatment_process_rule_docs()

	applicable_rules = []
	for rule in rules:
		rule_dict = rule.get_applicable_rule_dict(filters)
		if rule_dict:
			applicable_rules.append(rule_dict)

	return applicable_rules


def get_pretreatment_process_rule_docs():
	names = get_pretreatment_process_rule_names()
	docs = [frappe.get_cached_doc("Pretreatment Process Rule", name) for name in names]
	return docs


def get_pretreatment_process_rule_names():
	def generator():
		names = [d.name for d in frappe.get_all('Pretreatment Process Rule')]
		return names

	return frappe.cache().get_value("pretreatment_process_rule_names", generator)


def clear_pretreatment_process_rule_cache():
	frappe.cache().delete_value('pretreatment_process_rule_names')
