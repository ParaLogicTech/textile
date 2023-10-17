# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from textile.controllers.textile_order import TextileOrder
from frappe.utils import cint, flt, round_up
from textile.utils import pretreatment_components, get_textile_conversion_factors, validate_textile_item
from frappe.model.mapper import get_mapped_doc
from frappe.desk.notifications import clear_doctype_notifications
from erpnext.manufacturing.doctype.work_order.work_order import create_work_orders, get_subcontractable_qty
from textile.fabric_pretreatment.doctype.pretreatment_process_rule.pretreatment_process_rule import get_pretreatment_process_values


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
			self.set_progress_data_onload()
			self.set_onload('disallow_on_submit', self.get_disallow_on_submit_fields())

		self.set_fabric_stock_qty()

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
		self.set_status()

		self.set_title(self.greige_fabric_material, self.stock_qty)

	def before_update_after_submit(self):
		self.validate_dates()
		self.get_disallow_on_submit_fields()

		self._before_change = frappe.db.get_value(self.doctype, self.name, ["delivery_required", "packing_slip_required"],
			as_dict=1)

	def on_update_after_submit(self):
		self.handle_delivery_required_changed()
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_status(update=True)

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

	def set_progress_data_onload(self):
		totals = frappe.db.sql("""
			select
				sum(qty) as qty,
				sum(producible_qty) as producible_qty,
				sum(material_transferred_for_manufacturing) as material_transferred_for_manufacturing,
				sum(produced_qty) as produced_qty,
				sum(subcontract_order_qty) as subcontract_order_qty,
				sum(subcontract_received_qty) as subcontract_received_qty
			from `tabWork Order`
			where pretreatment_order = %s and docstatus = 1
		""", self.name, as_dict=1)

		totals = totals[0] if totals else frappe._dict()
		self.set_onload("progress_data", {
			"qty": flt(totals.qty) or flt(self.stock_qty),
			"stock_uom": self.stock_uom,
			"producible_qty": flt(totals.producible_qty),
			"material_transferred_for_manufacturing": flt(totals.material_transferred_for_manufacturing),
			"produced_qty": flt(totals.produced_qty),
			"subcontract_order_qty": flt(totals.subcontract_order_qty),
			"subcontract_received_qty": flt(totals.subcontract_received_qty),
		})

	def get_disallow_on_submit_fields(self):
		if self.cant_change_delivery_required():
			self.flags.disallow_on_submit = [("delivery_required", None), ("packing_slip_required", None)]

		return self.flags.disallow_on_submit or []

	def set_missing_values(self):
		self.set_fabric_item_details()

	def set_fabric_item_details(self):
		ready_details = get_fabric_item_details(self.greige_fabric_item, prefix="greige_", get_default_process=False)
		for k, v in ready_details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

		ready_details = get_fabric_item_details(self.ready_fabric_item, prefix="ready_", get_default_process=False)
		for k, v in ready_details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_fabric_stock_qty(self, prefix=None):
		super().set_fabric_stock_qty(prefix or "greige_")

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

	def start_pretreatment_order(self):
		frappe.flags.skip_pretreatment_order_status_update = True

		# Ready Fabric BOM
		if not self.ready_fabric_bom:
			self.create_ready_fabric_bom(ignore_version=True, ignore_feed=True)

		# Sales Order
		if flt(self.per_ordered) < 100 and not self.is_internal_customer:
			sales_order = _make_sales_order(self.name, ignore_permissions=True)
			sales_order.flags.ignore_version = True
			sales_order.flags.ignore_feed = True
			sales_order.flags.ignore_permissions = True
			sales_order.save()
			sales_order.submit()

			sales_order_msg = _("Sales Order created: {0}").format(
				frappe.utils.get_link_to_form("Sales Order", sales_order.name)
			)
			frappe.msgprint(sales_order_msg)

		# Work Order
		if flt(self.per_work_ordered) < 100:
			self.create_work_order(ignore_version=True, ignore_feed=True)

		# Status Update
		frappe.flags.skip_pretreatment_order_status_update = False

		self.set_sales_order_status(update=True)
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_status(update=True)

		self.validate_ordered_qty()
		self.validate_work_order_qty()

		self.notify_update()

	def create_ready_fabric_bom(self, ignore_version=True, ignore_feed=True):
		bom_doc = self.make_ready_fabric_bom()
		bom_doc.flags.ignore_version = ignore_version
		bom_doc.flags.ignore_feed = ignore_feed
		bom_doc.flags.ignore_permissions = True
		bom_doc.save()
		bom_doc.submit()

		self.db_set("ready_fabric_bom", bom_doc.name)

		frappe.msgprint(_("Ready Fabric {0} created successfully").format(
			frappe.get_desk_link("BOM", bom_doc.name))
		)

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
			"do_not_explode": 1,
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

	def create_work_order(self, ignore_version=True, ignore_feed=True):
		if self.docstatus != 1:
			frappe.throw(_("Pretreatment Order is not submitted"))

		if not self.ready_fabric_bom:
			frappe.throw(_("Ready Fabric BOM not created"))

		if self.is_internal_customer:
			wo_list = self.create_work_order_against_pretreatment_order(ignore_version=ignore_version, ignore_feed=ignore_feed)
		else:
			wo_list = self.create_work_order_against_sales_order(ignore_version=ignore_version, ignore_feed=ignore_feed)

		if wo_list:
			wo_message = _("Work Order created: {0}").format(
				", ".join([frappe.utils.get_link_to_form('Work Order', wo) for wo in wo_list])
			)
			frappe.msgprint(wo_message, indicator='green')

		return wo_list

	def create_work_order_against_pretreatment_order(self, ignore_version=True, ignore_feed=True):
		pending_qty = flt(self.stock_qty) - flt(self.work_order_qty)
		pending_qty = round_up(pending_qty, frappe.get_precision("Work Order", "qty"))

		if pending_qty <= 0:
			frappe.msgprint(_("Work Order already created"))
			return

		work_order_item = {
			"pretreatment_order": self.name,
			"item_code": self.ready_fabric_item,
			"item_name": self.ready_fabric_item_name,
			"bom_no": self.ready_fabric_bom,
			"warehouse": self.fg_warehouse,
			"production_qty": pending_qty,
			"customer": self.customer,
			"customer_name": self.customer_name,
		}

		return create_work_orders([work_order_item], self.company, ignore_version=ignore_version,
			ignore_feed=ignore_feed)

	def create_work_order_against_sales_order(self, ignore_version=True, ignore_feed=True):
		sales_orders = frappe.get_all("Sales Order Item", 'distinct parent as sales_order', {
			'pretreatment_order': self.name,
			'docstatus': 1
		}, pluck="sales_order")

		if not sales_orders:
			frappe.throw(_("Please create Sales Order first"))

		wo_items = []
		for so in sales_orders:
			so_doc = frappe.get_doc('Sales Order', so)
			wo_items += so_doc.get_work_order_items(item_condition=lambda d: d.pretreatment_order == self.name)

		wo_list = []
		for i, d in enumerate(wo_items):
			wo_list += create_work_orders([d], self.company, ignore_version=ignore_version, ignore_feed=ignore_feed)

		if not wo_list:
			frappe.msgprint(_("Work Order already created"))

		return wo_list

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
		self.produced_qty = data.completed_qty
		self.packed_qty = data.packed_qty
		self.subcontractable_qty = data.subcontractable_qty

		stock_qty = flt(self.stock_qty, self.precision("qty"))
		work_order_qty = flt(self.work_order_qty, self.precision("qty"))
		produced_qty = flt(self.produced_qty, self.precision("qty"))
		packed_qty = flt(self.packed_qty, self.precision("qty"))

		self.per_work_ordered = flt(work_order_qty / stock_qty * 100 if stock_qty else 0, 3)
		self.per_produced = flt(produced_qty / stock_qty * 100 if stock_qty else 0, 3)
		self.per_packed = flt(packed_qty / stock_qty * 100 if stock_qty else 0, 3)

		production_within_allowance = self.per_work_ordered >= 100 and self.per_produced > 0 and not data.has_work_order_to_produce
		self.production_status = self.get_completion_status('per_produced', 'Produce',
			not_applicable=self.status == "Closed" or not self.per_work_ordered,
			within_allowance=production_within_allowance)

		packing_within_allowance = self.per_work_ordered >= 100 and self.per_packed > 0 and not data.has_work_order_to_pack
		self.packing_status = self.get_completion_status('per_packed', 'Pack',
			not_applicable=not self.delivery_required or not self.packing_slip_required or self.status == "Closed" or not self.per_produced,
			within_allowance=packing_within_allowance)

		if update:
			self.db_set({
				'work_order_qty': self.work_order_qty,
				'produced_qty': self.produced_qty,
				'packed_qty': self.packed_qty,
				'subcontractable_qty': self.subcontractable_qty,

				'per_work_ordered': self.per_work_ordered,
				'per_produced': self.per_produced,
				'per_packed': self.per_packed,

				'production_status': self.production_status,
				'packing_status': self.packing_status,
			}, update_modified=update_modified)

	def get_production_packing_data(self):
		out = frappe._dict()
		out.work_order_qty = 0
		out.producible_qty = 0
		out.material_transferred_for_manufacturing = 0
		out.produced_qty = 0
		out.completed_qty = 0
		out.scrap_qty = 0
		out.packed_qty = 0
		out.subcontractable_qty = 0
		out.has_work_order_to_pack = False
		out.has_work_order_to_produce = False

		if self.docstatus == 1:
			# Work Order
			work_order_data = frappe.db.sql("""
				SELECT qty, producible_qty,
					produced_qty, material_transferred_for_manufacturing, completed_qty, scrap_qty,
					production_status, packing_status, subcontracting_status
				FROM `tabWork Order`
				WHERE docstatus = 1 AND pretreatment_order = %s
			""", self.name, as_dict=1)

			for d in work_order_data:
				out.work_order_qty += flt(d.qty)
				out.producible_qty += flt(d.producible_qty)
				out.material_transferred_for_manufacturing += flt(d.material_transferred_for_manufacturing)
				out.produced_qty += flt(d.produced_qty)
				out.completed_qty += flt(d.completed_qty)
				out.scrap_qty += flt(d.scrap_qty)

				out.subcontractable_qty += max(get_subcontractable_qty(
					d.producible_qty,
					d.material_transferred_for_manufacturing,
					d.produced_qty,
					d.scrap_qty
				), 0)

				if d.production_status == "To Produce" or d.subcontracting_status == "To Receive":
					out.has_work_order_to_produce = True
				if d.packing_status != "Packed":
					out.has_work_order_to_pack = True

			# Packing Slips
			packed_data = frappe.db.sql("""
				SELECT sum(packed_qty * conversion_factor)
				FROM `tabSales Order Item`
				WHERE docstatus = 1 AND pretreatment_order = %s and item_code = %s
			""", (self.name, self.ready_fabric_item))

			if packed_data:
				out.packed_qty = flt(packed_data[0][0])

		return out

	def validate_work_order_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'work_order_qty', 'stock_qty',
			allowance_type="production", from_doctype=from_doctype, item_field="ready_fabric_item")

	def validate_packed_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'packed_qty', 'stock_qty',
			allowance_type="production", from_doctype=from_doctype, item_field="ready_fabric_item")

	def set_delivery_status(self, update=False, update_modified=True):
		data = self.get_delivered_status_data()
		self.delivered_qty = flt(data.delivered_qty)

		stock_qty = flt(self.stock_qty, self.precision("qty"))
		delivered_qty = flt(self.delivered_qty, self.precision("qty"))
		self.per_delivered = flt(delivered_qty / stock_qty * 100 if stock_qty else 0, 3)

		within_allowance = self.per_ordered >= 100 and self.per_delivered > 0 and not data.has_incomplete_delivery
		self.delivery_status = self.get_completion_status('per_delivered', 'Deliver',
			not_applicable=not self.delivery_required or self.status == "Closed", within_allowance=within_allowance)

		if update:
			self.db_set({
				'delivered_qty': self.delivered_qty,
				'per_delivered': self.per_delivered,
				'delivery_status': self.delivery_status,
			}, update_modified=update_modified)

	def get_delivered_status_data(self):
		out = frappe._dict()
		out.delivered_qty = 0
		out.has_incomplete_delivery = False

		if self.docstatus == 1:
			delivered_data = frappe.db.sql("""
				SELECT sum(delivered_qty * conversion_factor)
				FROM `tabSales Order Item`
				WHERE docstatus = 1 AND pretreatment_order = %s and item_code = %s
			""", (self.name, self.ready_fabric_item))
			if delivered_data:
				out.delivered_qty = flt(delivered_data[0][0])

			sales_orders_to_deliver = frappe.db.sql_list("""
				select count(so.name)
				from `tabSales Order Item` i
				inner join `tabSales Order` so on so.name = i.parent
				where so.docstatus = 1 and so.delivery_status = 'To Deliver' and i.pretreatment_order = %s
			""", self.name)
			sales_orders_to_deliver = cint(sales_orders_to_deliver[0]) if sales_orders_to_deliver else 0
			if sales_orders_to_deliver:
				out.has_incomplete_delivery = True

		return out

	def validate_delivered_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'delivered_qty', 'stock_qty',
			allowance_type="qty", from_doctype=from_doctype, item_field="ready_fabric_item")

	def update_status_on_cancel(self):
		self.db_set({
			"status": "Cancelled",
			"production_status": "Not Applicable",
			"packing_status": "Not Applicable",
			"delivery_status": "Not Applicable",
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
			elif self.per_work_ordered < 100:
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

	def update_status(self, status):
		self.set_status(status=status)
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_status(update=True, status=status)
		self.notify_update()
		clear_doctype_notifications(self)

	def cant_change_delivery_required(self):
		if self.status == "Closed" or self.is_internal_customer:
			return True

		has_packing_slip = frappe.db.exists("Packing Slip Item", {"pretreatment_order": self.name, "docstatus": ["<", 2]})
		if has_packing_slip:
			return True

		has_delivery_note = frappe.db.exists("Delivery Note Item", {"pretreatment_order": self.name, "docstatus": ["<", 2]})
		if has_delivery_note:
			return True

		is_sales_order_closed = frappe.db.sql("""
			select so.name
			from `tabSales Order Item` i
			inner join `tabSales Order` so on so.name = i.parent
			where so.docstatus = 1 and so.status = 'Closed' and i.pretreatment_order = %s
			limit 1
		""", self.name)
		if is_sales_order_closed:
			return True

	def handle_delivery_required_changed(self):
		# Update Work Orders packing_slip_required
		if self.delivery_required != self._before_change.delivery_required or self.packing_slip_required != self._before_change.packing_slip_required:
			work_orders = frappe.get_all("Work Order",
				filters={"pretreatment_order": self.name},
				pluck="name"
			)
			for name in work_orders:
				work_order = frappe.get_doc("Work Order", name)
				work_order.db_set({
					"packing_slip_required": cint(self.delivery_required and self.packing_slip_required),
				})
				if work_order.docstatus == 1:
					work_order.set_packing_status(update=True)

				work_order.notify_update()

		# Update Sales Order skip_delivery_note
		if self.delivery_required != self._before_change.delivery_required:
			sales_orders = frappe.get_all("Sales Order Item",
				filters={"pretreatment_order": self.name, "docstatus": ["<", 2]},
				fields="distinct parent as sales_order",
				pluck="sales_order"
			)
			for name in sales_orders:
				sales_order = frappe.get_doc("Sales Order", name)
				for d in sales_order.items:
					if d.pretreatment_order == self.name:
						sales_order.set_skip_delivery_note_for_row(d, update=True)

				if sales_order.docstatus == 1:
					sales_order.set_skip_delivery_note_for_order(update=True)
					sales_order.set_delivery_status(update=True)
					sales_order.set_production_packing_status(update=True)
					sales_order.set_status(update=True)
					sales_order.update_reserved_qty()
					sales_order.notify_update()


def validate_transaction_against_pretreatment_order(doc):
	def get_order_details(name):
		if not order_map.get(name):
			order_map[name] = frappe.db.get_value("Pretreatment Order", name, [
				"name", "docstatus", "status", "company",
				"customer", "customer_name", "is_internal_customer",
				"fg_warehouse", "ready_fabric_item", "greige_fabric_item",
			], as_dict=1)

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

		if order_details.is_internal_customer:
			frappe.throw(_("Row #{0}: Cannot create {1} against {2} because it is against an internal customer {3}").format(
				d.idx,
				doc.doctype,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				frappe.bold(order_details.customer_name or order_details.customer)
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
				order_details.customer_name or order_details.customer
			))

		if d.get("is_return_fabric"):
			if d.item_code != order_details.greige_fabric_item:
				frappe.throw(_("Row #{0}: Return Fabric Item does not match with {1}. Item Code must be {2}").format(
					d.idx,
					frappe.get_desk_link("Pretreatment Order", order_details.name),
					order_details.greige_fabric_item
				))
		else:
			if d.item_code != order_details.ready_fabric_item:
				frappe.throw(_("Row #{0}: Item Code does not match with {1}. Item Code must be {2}").format(
					d.idx,
					frappe.get_desk_link("Pretreatment Order", order_details.name),
					order_details.ready_fabric_item
				))

		if doc.doctype == "Sales Order" and d.warehouse != order_details.fg_warehouse:
			frappe.throw(_("Row #{0}: Warehouse does not match with {1}. Warehouse must be {2}").format(
				d.idx,
				frappe.get_desk_link("Pretreatment Order", order_details.name),
				order_details.warehouse
			))


@frappe.whitelist()
def get_fabric_item_details(fabric_item, prefix=None, get_ready_fabric=False, get_greige_fabric=False,
		get_default_process=True):
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

	if fabric_item and cint(get_default_process):
		process_details = get_default_pretreatment_process(fabric_item)
		out.update(process_details)

	return out


@frappe.whitelist()
def get_default_pretreatment_process(fabric_item):
	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()
	out = frappe._dict()

	for component_item_field in pretreatment_components:
		out[component_item_field] = None
		out[f"{component_item_field}_name"] = None

	# Set process components from rules
	print_process_defaults = get_pretreatment_process_values(fabric_doc.name)
	out.update(print_process_defaults)

	return out


@frappe.whitelist()
def start_pretreatment_order(pretreatment_order):
	doc = frappe.get_doc('Pretreatment Order', pretreatment_order)

	if doc.docstatus != 1:
		frappe.throw(_("Pretreatment Order {0} is not submitted").format(doc.name))
	if doc.status == "Closed":
		frappe.throw(_("Pretreatment Order {0} is Closed").format(doc.name))

	doc.start_pretreatment_order()


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

	doc.create_ready_fabric_bom()
	doc.notify_update()


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
		target.conversion_factor = flt(source_parent.conversion_factor)
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
def create_work_order(pretreatment_order):
	doc = frappe.get_doc('Pretreatment Order', pretreatment_order)
	doc.create_work_order()


@frappe.whitelist()
def make_packing_slip(source_name, target_doc=None):
	from erpnext.selling.doctype.sales_order.sales_order import make_packing_slip

	doc = frappe.get_doc("Pretreatment Order", source_name)

	selected_children = frappe.get_all("Sales Order Item", filters={"pretreatment_order": doc.name}, pluck="name")
	frappe.flags.selected_children = {"items": selected_children}

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.per_packed < 100 and i.skip_delivery_note = 0
			AND s.company = %(company)s AND i.pretreatment_order = %(pretreatment_order)s
	""", {"pretreatment_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be packed"))

	for d in sales_orders:
		target_doc = make_packing_slip(d.name, target_doc=target_doc)

	return target_doc


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note_from_packing_slips

	doc = frappe.get_doc("Pretreatment Order", source_name)

	selected_children = frappe.get_all("Sales Order Item", filters={"pretreatment_order": doc.name}, pluck="name")
	frappe.flags.selected_children = {"items": selected_children}

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.per_delivered < 100 AND i.skip_delivery_note = 0
			AND s.company = %(company)s AND i.pretreatment_order = %(pretreatment_order)s
	""", {"pretreatment_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be delivered"))

	packing_filter = "Packed Items Only" if doc.packing_slip_required else None

	for d in sales_orders:
		target_doc = make_delivery_note_from_packing_slips(d.name, target_doc=target_doc, packing_filter=packing_filter)

	return target_doc


@frappe.whitelist()
def make_print_order(source_name):
	pretreatment_order = frappe.get_doc('Pretreatment Order', source_name)

	if pretreatment_order.docstatus != 1:
		frappe.throw(_("Pretreatment Order {0} is not submitted").format(pretreatment_order.name))
	if pretreatment_order.is_internal_customer:
		frappe.throw(_("Cannot make Print Order against Pretreatment Order for internal customer"))
	if pretreatment_order.status == "Closed":
		frappe.throw(_("Pretreatment Order {0} is Closed").format(pretreatment_order.name))

	print_order = frappe.new_doc("Print Order")
	print_order.pretreatment_order = pretreatment_order.name
	print_order.customer = pretreatment_order.customer
	print_order.is_fabric_provided_by_customer = pretreatment_order.is_fabric_provided_by_customer
	print_order.fabric_item = pretreatment_order.ready_fabric_item
	print_order.fabric_warehouse = pretreatment_order.fg_warehouse

	print_order.run_method("set_missing_values", get_default_process=True)

	return print_order


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):
	from erpnext.manufacturing.doctype.work_order.work_order import make_purchase_order

	pretreatment_order = frappe.db.get_value("Pretreatment Order", source_name,
		["name", "docstatus", "status"], as_dict=1)

	if not pretreatment_order:
		frappe.throw(_("Pretreatment Order {0} does not exist").format(source_name))
	if pretreatment_order.docstatus != 1:
		frappe.throw(_("Pretreatment Order {0} is not submitted").format(pretreatment_order.name))
	if pretreatment_order.status == "Closed":
		frappe.throw(_("Pretreatment Order {0} is {1}").format(pretreatment_order.name, pretreatment_order.status))

	work_orders = frappe.get_all("Work Order", {
		"docstatus": 1, "pretreatment_order": source_name
	}, pluck="name")
	if not work_orders:
		frappe.throw(_("There are no Work Orders against Pretreatment Order {0}").format(pretreatment_order.name))

	return make_purchase_order(work_orders, target_doc)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_pretreatment_orders_to_be_delivered(doctype, txt, searchfield, start, page_len, filters, as_dict):
	return _get_pretreatment_orders_to_be_delivered(doctype, txt, searchfield, start, page_len, filters, as_dict)


def _get_pretreatment_orders_to_be_delivered(doctype="Pretreatment Order", txt="", searchfield="name", start=0, page_len=0,
		filters=None, as_dict=True, ignore_permissions=False):
	from frappe.desk.reportview import get_match_cond, get_filters_cond
	from erpnext.controllers.queries import get_fields

	fields = get_fields("Pretreatment Order")
	select_fields = ", ".join(["`tabPretreatment Order`.{0}".format(f) for f in fields])
	limit = "limit {0}, {1}".format(start, page_len) if page_len else ""

	if not filters:
		filters = {}

	return frappe.db.sql("""
		select {fields}
		from `tabPretreatment Order`
		where `tabPretreatment Order`.docstatus = 1
			and `tabPretreatment Order`.`status` != 'Closed'
			and ifnull(`tabPretreatment Order`.`ready_fabric_bom`, '') != ''
			and `tabPretreatment Order`.`delivery_status` = 'To Deliver'
			and `tabPretreatment Order`.`{key}` like {txt}
			and `tabPretreatment Order`.`per_delivered` < `tabPretreatment Order`.`per_produced`
			and (`tabPretreatment Order`.`packing_slip_required` = 0 or `tabPretreatment Order`.`per_delivered` < `tabPretreatment Order`.`per_packed`)
			{fcond} {mcond}
		order by `tabPretreatment Order`.transaction_date, `tabPretreatment Order`.creation
		{limit}
	""".format(
		fields=select_fields,
		key=searchfield,
		fcond=get_filters_cond(doctype, filters, [], ignore_permissions=ignore_permissions),
		mcond="" if ignore_permissions else get_match_cond(doctype),
		limit=limit,
		txt="%(txt)s",
	), {"txt": ("%%%s%%" % txt)}, as_dict=as_dict)
