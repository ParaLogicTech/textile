# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.model.document import Document
from textile.utils import validate_textile_item, printing_components

filter_fields = ['fabric_material', 'fabric_type']


class PrintProcessRule(Document):
	def validate(self):
		self.validate_duplicate()
		self.validate_process_item()

	def on_change(self):
		clear_print_process_rule_cache()

	def after_rename(self, old_name, new_name, merge):
		clear_print_process_rule_cache()

	def validate_process_item(self):
		if self.get("process_item"):
			validate_textile_item(self.process_item, "Print Process")

		for component_item_field, component_type in printing_components.items():
			if self.get(f"{component_item_field}_required"):
				if self.get(component_item_field):
					validate_textile_item(self.get(component_item_field), "Process Component", component_type)
			else:
				self.set(component_item_field, None)
				self.set(f"{component_item_field}_name", None)

	def validate_duplicate(self):
		filters = {}

		if not self.is_new():
			filters['name'] = ['!=', self.name]

		for f in filter_fields:
			if self.get(f):
				filters[f] = self.get(f)
			else:
				filters[f] = ['is', 'not set']

		existing = frappe.get_all("Print Process Rule", filters=filters)
		if existing:
			frappe.throw(_("{0} already exists with the same filters")
				.format(frappe.get_desk_link("Print Process Rule", existing[0].name)))

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


def get_print_process_values(fabric_item):
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

	component_required_fields = [f"{component_item_field}_required" for component_item_field in printing_components]

	rule_meta = frappe.get_meta("Print Process Rule")
	values = frappe._dict()
	for rule in applicable_rules:
		for fieldname, value in rule.items():
			if fieldname == "print_process_rule_name":
				continue
			if fieldname in component_required_fields:
				continue

			if value and fieldname not in filter_fields and rule_meta.has_field(fieldname):
				if not values.get(fieldname):
					values[fieldname] = value

	if values.get("process_item"):
		process_item_doc = frappe.get_cached_doc("Item", values.process_item)
		for component_item_field in printing_components:
			if not process_item_doc.get(f"{component_item_field}_required"):
				values.pop(component_item_field, None)
				values.pop(f"{component_item_field}_name", None)

	return values


def get_applicable_rules(fabric_item):
	filters = get_filters_dict(fabric_item)
	return get_applicable_rules_for_filters(filters)


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

	rules = get_print_process_rule_docs()

	applicable_rules = []
	for rule in rules:
		rule_dict = rule.get_applicable_rule_dict(filters)
		if rule_dict:
			applicable_rules.append(rule_dict)

	return applicable_rules


def get_print_process_rule_docs():
	names = get_print_process_rule_names()
	docs = [frappe.get_cached_doc("Print Process Rule", name) for name in names]
	return docs


def get_print_process_rule_names():
	def generator():
		names = [d.name for d in frappe.get_all('Print Process Rule')]
		return names

	return frappe.cache().get_value("print_process_rule_names", generator)


def clear_print_process_rule_cache():
	frappe.cache().delete_value('print_process_rule_names')


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def paper_item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	from erpnext.controllers.queries import item_query

	if not filters:
		filters = {}

	filters["textile_item_type"] = "Process Component"

	process_component = filters.pop("process_component", None)
	fabric_item = filters.pop("fabric_item", None)

	if not process_component:
		frappe.throw(_("Process Component not provided"))
	if not fabric_item:
		frappe.throw(_("Fabric Item not provided"))

	fabric_width = frappe.get_cached_value("Item", fabric_item, "fabric_width")

	papers = get_applicable_papers(process_component, fabric_width)
	paper_item_codes = [d.name for d in papers]

	if paper_item_codes:
		filters["name"] = ("in", paper_item_codes)

	return item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=as_dict)


def get_applicable_papers(process_component, fabric_width):
	fabric_width = flt(fabric_width)

	items = frappe.get_all("Item", fields=["name", "item_name", "paper_width"], filters={
		"textile_item_type": "Process Component",
		"process_component": process_component,
		"paper_width": [">", fabric_width],
		"disabled": 0,
	}, order_by="paper_width")

	if not items:
		return []

	if not fabric_width:
		return items

	smallest_width = cint(items[0].paper_width)
	if not smallest_width:
		return items

	smallest_width_items = [d for d in items if cint(d.paper_width) == smallest_width]
	return smallest_width_items
