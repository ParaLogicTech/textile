# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from textile.controllers.textile_order import TextileOrder
from frappe.utils import cint, flt, cstr
from textile.utils import pretreatment_components, get_textile_conversion_factors, validate_textile_item


force_customer_fields = ["customer_name"]
force_fabric_fields = ["fabric_item_name", "fabric_material", "fabric_type", "fabric_width", "fabric_gsm", "fabric_per_pickup"]
force_process_component_fields = (
	[f"{component_item_field}_name" for component_item_field in pretreatment_components]
	+ [f"{component_item_field}_by_fabric_weight" for component_item_field in pretreatment_components]
)

force_fields = force_customer_fields + force_fabric_fields + force_process_component_fields


class PretreatmentOrder(TextileOrder):
	def get_feed(self):
		if self.get("title"):
			return self.title

	def onload(self):
		if self.docstatus == 0:
			self.set_missing_values()
			self.calculate_totals()

		self.set_fabric_stock_qty("greige_")

	def validate(self):
		self.set_missing_values()
		self.validate_dates()
		self.validate_customer()
		self.validate_fabric_items()
		self.validate_process_items()
		self.calculate_totals()
		self.set_existing_ready_fabric_bom()

		self.set_status()

		self.set_title(self.greige_fabric_material, self.stock_qty)

	def on_submit(self):
		self.link_greige_fabric_in_ready_fabric()

	def set_missing_values(self):
		self.set_fabric_item_details()

	def set_fabric_item_details(self):
		ready_details = get_fabric_item_details(self.greige_fabric_item, prefix="greige_")
		for k, v in ready_details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

		ready_details = get_fabric_item_details(self.ready_fabric_item, prefix="ready_")
		for k, v in ready_details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def validate_fabric_items(self):
		self.validate_fabric_item("Greige Fabric", "greige_")
		self.validate_fabric_item("Ready Fabric", "ready_")

		if self.greige_fabric_item and self.ready_fabric_item:
			greige_fabric_details = frappe.get_cached_value("Item", self.greige_fabric_item,
				["fabric_material", "fabric_type"], as_dict=1)
			ready_fabric_details = frappe.get_cached_value("Item", self.ready_fabric_item,
				["fabric_material", "fabric_type"], as_dict=1)

			if greige_fabric_details.fabric_material != ready_fabric_details.fabric_material:
				frappe.throw(_("Greige Fabric Material {0} does not match with Ready Fabric Material {1}").format(
					frappe.bold(greige_fabric_details.fabric_material), frappe.bold(ready_fabric_details.fabric_material)
				))
			if greige_fabric_details.fabric_type != ready_fabric_details.fabric_type:
				frappe.throw(_("Greige Fabric Type {0} does not match with Ready Fabric Type {1}").format(
					frappe.bold(greige_fabric_details.fabric_type), frappe.bold(ready_fabric_details.fabric_type)
				))

	def validate_process_items(self):
		for component_item_field, component_type in pretreatment_components.items():
			if self.get(component_item_field):
				validate_textile_item(self.get(component_item_field), "Process Component", component_type)

		if self.docstatus == 1:
			process_mandatory = {
				"bleaching_item": True,
				"desizing_item": frappe.get_cached_value("Fabric Pretreatment Settings", None, "desizing_mandatory"),
				"singeing_item": frappe.get_cached_value("Fabric Pretreatment Settings", None, "singeing_mandatory"),
			}

			# Check Process Component Mandatory
			for component_item_field, is_mandatory in process_mandatory.items():
				if is_mandatory and not self.get(component_item_field):
					field_label = self.meta.get_label(component_item_field)
					frappe.throw(_("{0} is mandatory for submission").format(frappe.bold(field_label)))

			# Check GSM/Pickup mandatory for consumption by weight
			for component_item_field in pretreatment_components:
				component_item = self.get(component_item_field)
				if not component_item:
					continue

				field_label = self.meta.get_label(component_item_field)
				component_item_name = self.get(f"{component_item_field}_name") or component_item

				if self.get(f"{component_item_field}_by_fabric_weight"):
					if not self.greige_fabric_gsm:
						frappe.throw(_("Greige Fabric GSM is mandatory for {0} {1}. Please set Fabric GSM in {2}").format(
							field_label,
							frappe.bold(component_item_name),
							frappe.get_desk_link("Item", self.greige_fabric_item)
						))
					if not self.greige_fabric_per_pickup:
						frappe.throw(_("Greige Fabric Pickup % is mandatory for {0} {1}. Please set Fabric Pickup % in {2}").format(
							field_label,
							frappe.bold(component_item_name),
							frappe.get_desk_link("Item", self.greige_fabric_item)
						))

	def calculate_totals(self):
		self.round_floats_in(self)

		conversion_factors = get_textile_conversion_factors()
		uom_to_convert = self.uom + '_to_' + self.stock_uom
		uom_to_convert = uom_to_convert.lower()
		conversion_factor = conversion_factors[uom_to_convert] or 1

		self.stock_qty = self.qty * conversion_factor

	def link_greige_fabric_in_ready_fabric(self):
		linked_greige_fabric = frappe.db.get_value("Item", self.ready_fabric_item, "fabric_item")
		if linked_greige_fabric != self.greige_fabric_item:
			ready_fabric_doc = frappe.get_doc("Item", self.ready_fabric_item)
			ready_fabric_doc.fabric_item = self.greige_fabric_item
			ready_fabric_doc.save(ignore_permissions=True)

	def create_ready_fabric_bom(self, ignore_version=True, ignore_feed=True):
		bom_doc = self.make_ready_fabric_bom()
		bom_doc.flags.ignore_version = ignore_version
		bom_doc.flags.ignore_feed = ignore_feed
		bom_doc.flags.ignore_permissions = True
		bom_doc.save()
		bom_doc.submit()

		self.db_set("ready_fabric_bom", bom_doc.name)
		return bom_doc.name

	def make_ready_fabric_bom(self):
		if not self.greige_fabric_item:
			frappe.throw(_('Greige Fabric Item is mandatory'))
		if not self.ready_fabric_item:
			frappe.throw(_('Ready Fabric Item is mandatory'))

		bom_doc = frappe.new_doc("BOM")
		bom_doc.update({
			"item": self.ready_fabric_item,
			"quantity": 1,
		})

		self.validate_item_convertible_to_uom(self.greige_fabric_item, "Meter")
		bom_doc.append("items", {
			"item_code": self.greige_fabric_item,
			"qty": 1,
			"uom": "Meter",
			"skip_transfer_for_manufacture": 0,
		})

		components = []
		for component_item_field in pretreatment_components:
			if self.get(component_item_field):
				component = frappe._dict({
					"item_code": self.get(component_item_field),
					"consumption_by_fabric_weight": cint(self.get(f"{component_item_field}_by_fabric_weight"))
				})

				components.append(component)

		self.add_components_to_bom(bom_doc, components, self.greige_fabric_gsm, self.greige_fabric_width,
			self.greige_fabric_per_pickup)

		return bom_doc

	def set_existing_ready_fabric_bom(self):
		self.ready_fabric_bom = self.get_existing_ready_fabric_bom()

	def get_existing_ready_fabric_bom(self):
		if not self.ready_fabric_item or not self.greige_fabric_item:
			return None

		filters = frappe._dict({
			"name": self.name,
			"ready_fabric_item": self.ready_fabric_item,
			"greige_fabric_item": self.greige_fabric_item,
			"greige_fabric_gsm": self.greige_fabric_gsm,
			"greige_fabric_width": self.greige_fabric_width,
			"greige_fabric_per_pickup": self.greige_fabric_per_pickup,
		})

		process_conditions = []

		for component_item_field in pretreatment_components:
			component_item_code = self.get(component_item_field)
			if component_item_code:
				process_conditions.append(f"p.{component_item_field} = %({component_item_field})s")

				if self.meta.has_field(f"{component_item_field}_by_fabric_weight"):
					process_conditions.append(f"p.{component_item_field}_by_fabric_weight = %({component_item_field}_by_fabric_weight)s")

					if self.get(f"{component_item_field}_by_fabric_weight"):
						process_conditions.append("p.greige_fabric_gsm = %(greige_fabric_gsm)s")
						process_conditions.append("p.greige_fabric_per_pickup = %(greige_fabric_per_pickup)s")
						process_conditions.append("p.greige_fabric_width = %(greige_fabric_width)s")
			else:
				process_conditions.append(f"ifnull(p.{component_item_field}, '') = ''")

			filters[component_item_field] = component_item_code
			filters[f"{component_item_field}_by_fabric_weight"] = cint(self.get(f"{component_item_field}_by_fabric_weight"))

		process_conditions = f" AND {' AND '.join(process_conditions)}"

		existing_bom = frappe.db.sql_list("""
			SELECT p.ready_fabric_bom
			FROM `tabPretreatment Order` p
			WHERE p.name != %(name)s
				AND p.ready_fabric_item = %(ready_fabric_item)s
				AND p.greige_fabric_item = %(greige_fabric_item)s
				AND ifnull(p.ready_fabric_bom, '') != ''
				{0}
			ORDER BY p.creation DESC
			LIMIT 1
			""".format(process_conditions), filters)

		return existing_bom[0] if existing_bom else None


@frappe.whitelist()
def get_fabric_item_details(fabric_item, prefix=None, get_ready_fabric=False, get_greige_fabric=False):
	from textile.utils import get_fabric_item_details

	get_ready_fabric = cint(get_ready_fabric)
	get_greige_fabric = cint(get_greige_fabric)

	out = get_fabric_item_details(fabric_item)
	if prefix:
		out = frappe._dict({f"{prefix}{key}": value for key, value in out.items()})

	if fabric_item and get_ready_fabric:
		ready_fabric_items = frappe.get_all("Item", filters={
			"textile_item_type": "Ready Fabric",
			"fabric_item": fabric_item,
			"disabled": 0,
		}, pluck="name")

		if len(ready_fabric_items) == 1:
			out.ready_fabric_item = ready_fabric_items[0]

	if fabric_item and get_greige_fabric:
		textile_item_type, greige_fabric_item = frappe.get_cached_value("Item", fabric_item,
			["textile_item_type", "fabric_item"])

		if textile_item_type == "Ready Fabric" and greige_fabric_item:
			out.greige_fabric_item = greige_fabric_item

	return out


@frappe.whitelist()
def create_ready_fabric_bom(pretreatment_order):
	if isinstance(pretreatment_order, str):
		doc = frappe.get_doc("Pretreatment Order", pretreatment_order)
	else:
		doc = pretreatment_order

	if doc.docstatus != 1:
		frappe.throw(_("Submit the Pretreatment Order first"))
	if doc.ready_fabric_bom:
		frappe.throw(_("Ready Fabric BOM already created"))

	bom_no = doc.create_ready_fabric_bom()
	doc.notify_update()

	frappe.msgprint(_("Ready Fabric {0} created successfully").format(
		frappe.get_desk_link("BOM", bom_no))
	)
