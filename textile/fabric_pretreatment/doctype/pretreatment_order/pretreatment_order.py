# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from textile.controllers.textile_order import TextileOrder
from frappe.utils import cint, flt
from textile.utils import pretreatment_components, get_textile_conversion_factors, validate_textile_item
from frappe.model.mapper import get_mapped_doc


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
		elif self.docstatus == 1:
			self.set_work_order_onload()

		self.set_fabric_stock_qty("greige_")

	def validate(self):
		self.set_missing_values()
		self.validate_dates()
		self.validate_customer()
		self.validate_fabric_items()
		self.validate_process_items()
		self.validate_qty()
		self.calculate_totals()
		self.set_existing_ready_fabric_bom()

		self.set_sales_order_status()
		self.set_production_packing_status()
		self.set_delivery_status()
		self.set_billing_status()
		self.set_status()

		self.set_title(self.greige_fabric_material, self.stock_qty)

	def on_submit(self):
		self.link_greige_fabric_in_ready_fabric()

	def on_cancel(self):
		if self.status == "Closed":
			frappe.throw(_("Closed Order cannot be cancelled. Re-open to cancel."))

		self.update_status_on_cancel()

	def set_work_order_onload(self):
		work_order = frappe.db.get_value("Work Order",
			filters={"pretreatment_order": self.name, "docstatus": ["<", 2]},
			order_by="docstatus desc"
		)
		self.set_onload("work_order", work_order)

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

	def validate_qty(self):
		if flt(self.qty) <= 0:
			frappe.throw(_("Qty must be greater than 0"))

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

	def set_sales_order_status(self, update=False, update_modified=True):
		sales_order_data = frappe.db.sql("""
			select sum(stock_qty)
			from `tabSales Order Item`
			where docstatus = 1 and pretreatment_order = %s
		""", self.name)

		self.ordered_qty = flt(sales_order_data[0][0]) if sales_order_data else 0

		ordered_qty = flt(self.ordered_qty, self.precision("qty"))
		stock_qty = flt(self.stock_qty, self.precision("qty"))
		self.per_ordered = flt(ordered_qty / stock_qty * 100 if stock_qty else 0, 3)

		if update:
			self.db_set({
				'ordered_qty': self.ordered_qty,
				'per_ordered': self.per_ordered,
			}, update_modified=update_modified)

	def validate_ordered_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'ordered_qty', 'stock_qty',
			from_doctype=from_doctype, item_field="ready_fabric_item")

	def set_production_packing_status(self, update=False, update_modified=True):
		data = self.get_production_packing_data()

		self.work_order_qty = data.work_order_qty
		self.produced_qty = data.produced_qty
		self.packed_qty = data.packed_qty

		stock_qty = flt(self.stock_qty, self.precision("qty"))
		work_order_qty = flt(self.work_order_qty, self.precision("qty"))
		produced_qty = flt(self.produced_qty, self.precision("qty"))
		packed_qty = flt(self.packed_qty, self.precision("qty"))

		self.per_work_ordered = flt(work_order_qty / stock_qty * 100 if stock_qty else 0, 3)
		self.per_produced = flt(produced_qty / stock_qty * 100 if stock_qty else 0, 3)
		self.per_packed = flt(packed_qty / stock_qty * 100 if stock_qty else 0, 3)

		production_within_allowance = self.per_work_ordered >= 100 and self.per_produced > 0 and not data.has_work_order_to_produce
		self.production_status = self.get_completion_status('per_produced', 'Produce',
			not_applicable=self.status == "Closed" or not self.per_ordered,
			within_allowance=production_within_allowance)

		packing_within_allowance = self.per_ordered >= 100 and self.per_packed > 0 and not data.has_work_order_to_pack
		self.packing_status = self.get_completion_status('per_packed', 'Pack',
			not_applicable=self.status == "Closed" or not self.packing_slip_required or not self.per_produced,
			within_allowance=packing_within_allowance)

		if update:
			self.db_set({
				'work_order_qty': self.work_order_qty,
				'produced_qty': self.produced_qty,
				'packed_qty': self.packed_qty,

				'per_work_ordered': self.per_work_ordered,
				'per_produced': self.per_produced,
				'per_packed': self.per_packed,

				'production_status': self.production_status,
				'packing_status': self.packing_status,
			}, update_modified=update_modified)

	def get_production_packing_data(self):
		out = frappe._dict()
		out.work_order_qty = 0
		out.produced_qty = 0
		out.packed_qty = 0
		out.has_work_order_to_pack = False
		out.has_work_order_to_produce = False

		if self.docstatus == 1:
			# Work Order
			work_order_data = frappe.db.sql("""
				SELECT qty, produced_qty, production_status, packing_status
				FROM `tabWork Order`
				WHERE docstatus = 1 AND pretreatment_order = %s
			""", self.name, as_dict=1)

			for d in work_order_data:
				out.work_order_qty += flt(d.qty)
				out.produced_qty += flt(d.produced_qty)

				if d.production_status != "Produced":
					out.has_work_order_to_produce = True
				if d.packing_status != "Packed":
					out.has_work_order_to_pack = True

			# Packing Slips
			packed_data = frappe.db.sql("""
				SELECT sum(stock_qty)
				FROM `tabPacking Slip Item`
				WHERE docstatus = 1 AND pretreatment_order = %s and item_code = %s
			""", (self.name, self.ready_fabric_item))

			if packed_data:
				out.packed_qty = flt(packed_data[0][0])

		return out

	def validate_work_order_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'work_order_qty', 'stock_qty',
			allowance_type="production", from_doctype=from_doctype, item_field="ready_fabric_item")

	def set_delivery_status(self, update=False, update_modified=True):
		pass

	def set_billing_status(self, update=False, update_modified=True):
		pass

	def update_status_on_cancel(self):
		self.db_set({
			"status": "Cancelled",
			"production_status": "Not Applicable",
			"packing_status": "Not Applicable",
			"delivery_status": "Not Applicable",
			"billing_status": "Not Applicable",
		})

	def set_status(self, status=None, update=False, update_modified=True):
		previous_status = self.status

		if status:
			self.status = status

		if self.docstatus == 0:
			self.status = "Draft"

		elif self.docstatus == 1:
			if self.status == "Closed":
				self.status = "Closed"
			elif self.per_ordered < 100:
				self.status = "Not Started"
			elif self.production_status == "To Produce":
				self.status = "To Produce"
			elif self.delivery_status == "To Deliver":
				self.status = "To Deliver"
			else:
				self.status = "Completed"

		else:
			self.status = "Cancelled"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)


def validate_transaction_against_pretreatment_order(doc):
	def get_order_details(name):
		if not order_map.get(name):
			order_map[name] = frappe.db.get_value("Pretreatment Order", name,
				["name", "docstatus", "status", "company", "customer", "fg_warehouse", "ready_fabric_item"], as_dict=1)

		return order_map[name]

	order_map = {}
	visited_orders = set()

	for d in doc.get("items"):
		if not d.get("pretreatment_order"):
			continue

		if doc.doctype == "Sales Order" and d.pretreatment_order in visited_orders:
			frappe.throw(_("Duplicate row {0} with same {1}").format(d.idx, _("Pretreatment Order")))
		else:
			visited_orders.add(d.pretreatment_order)

		order_details = get_order_details(d.pretreatment_order)
		if not order_details:
			frappe.throw(_("Row #{0}: Pretreatment Order {1} does not exist").format(d.idx, d.pretreatment_order))

		if order_details.docstatus == 0:
			frappe.throw(_("Row #{0}: {1} is in draft").format(
				d.idx, frappe.get_desk_link("Pretreatment Order", order_details.name)
			))
		if order_details.docstatus == 2:
			frappe.throw(_("Row #{0}: {1} is cancelled").format(
				d.idx, frappe.get_desk_link("Pretreatment Order", order_details.name)
			))

		if order_details.status == "Closed" and not doc.get("is_return"):
			frappe.throw(_("Row #{0}: {1} is {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				frappe.bold(order_details.status)
			))

		if doc.company != order_details.company:
			frappe.throw(_("Row #{0}: Company does not match with {1}. Company must be {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				order_details.company
			))

		if doc.customer != order_details.customer:
			frappe.throw(_("Row #{0}: Customer does not match with {1}. Customer must be {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				order_details.customer
			))

		if d.item_code != order_details.ready_fabric_item:
			frappe.throw(_("Row #{0}: Item Code does not match with {1}. Item Code must be {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				order_details.ready_fabric_item
			))

		if d.warehouse != order_details.fg_warehouse and doc.doctype == "Sales Order":
			frappe.throw(_("Row #{0}: Warehouse does not match with {1}. Warehouse must be {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				order_details.warehouse
			))


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


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	return _make_sales_order(source_name, target_doc)


def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	def set_missing_values(source, target):
		if item_condition(source, target):
			row = frappe.new_doc("Sales Order Item")
			update_item(row, source, target)
			target.append("items", row)

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_payment_schedule")

	def item_condition(source_parent, target_parent):
		if source_parent.name in [d.pretreatment_order for d in target_parent.get('items') if d.pretreatment_order]:
			return False

		return abs(source_parent.ordered_qty) < abs(source_parent.qty)

	def update_item(target, source_parent, target_parent):
		target.pretreatment_order = source_parent.name
		target.item_code = source_parent.ready_fabric_item
		target.qty = flt(source_parent.qty) - flt(source_parent.ordered_qty)
		target.uom = source_parent.uom

	doc = get_mapped_doc("Pretreatment Order", source_name, {
		"Pretreatment Order": {
			"doctype": "Sales Order",
			"field_map": {
				"delivery_date": "delivery_date",
				"fg_warehouse": "set_warehouse",
			},
			"validation": {
				"docstatus": ["=", 1],
			}
		},
	}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	return doc


@frappe.whitelist()
def create_work_order(pretreatment_order, ignore_version=True, ignore_feed=True):
	from erpnext.manufacturing.doctype.work_order.work_order import create_work_orders

	if isinstance(pretreatment_order, str):
		doc = frappe.get_doc('Pretreatment Order', pretreatment_order)
	else:
		doc = pretreatment_order

	if doc.docstatus != 1:
		frappe.throw(_("Pretreatment Order is not submitted"))

	if not doc.ready_fabric_bom:
		frappe.throw(_("Ready Fabric BOM not created"))

	sales_orders = frappe.get_all("Sales Order Item", 'distinct parent as sales_order', {
		'pretreatment_order': doc.name,
		'docstatus': 1
	}, pluck="sales_order")

	wo_items = []
	for so in sales_orders:
		so_doc = frappe.get_doc('Sales Order', so)
		wo_items += so_doc.get_work_order_items(item_condition=lambda d: d.pretreatment_order == pretreatment_order)

	wo_list = []
	for i, d in enumerate(wo_items):
		wo_list += create_work_orders([d], doc.company, ignore_version=ignore_version, ignore_feed=ignore_feed)

	if wo_list:
		wo_message = _("Work Order created: {0}").format(
			", ".join([frappe.utils.get_link_to_form('Work Order', wo) for wo in wo_list])
		)
		frappe.msgprint(wo_message, indicator='green')
	else:
		frappe.msgprint(_("Work Orders already created"))
