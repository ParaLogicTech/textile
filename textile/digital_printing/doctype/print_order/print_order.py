# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate
from frappe.model.mapper import get_mapped_doc
from frappe.desk.notifications import clear_doctype_notifications
from erpnext.accounts.party import validate_party_frozen_disabled
from erpnext.stock.get_item_details import get_bin_details, get_conversion_factor
from textile.digital_printing.doctype.print_process_rule.print_process_rule import print_process_components,\
	get_print_process_values, get_applicable_papers
from erpnext.controllers.status_updater import StatusUpdater
from PIL import Image
import json


default_fields_map = {
	"default_printing_uom": "default_uom",
	"default_printing_gap": "default_gap",
	"default_printing_qty_type": "default_qty_type",
	"default_printing_length_uom": "default_length_uom"
}

force_customer_fields = ["customer_name"]
force_fabric_fields = ["fabric_item_name", "fabric_material", "fabric_type", "fabric_width", "fabric_gsm"]
force_process_fields = ["process_item_name"] + [f"{component_item_field}_required" for component_item_field in print_process_components]

force_fields = force_customer_fields + force_fabric_fields + force_process_fields


class PrintOrder(StatusUpdater):
	def get_feed(self):
		if self.get("title"):
			return self.title

	def onload(self):
		if self.docstatus == 0:
			self.set_missing_values()
			self.calculate_totals()

		self.set_fabric_stock_qty()

	@frappe.whitelist()
	def on_upload_complete(self):
		self.set_missing_values()
		self.calculate_totals()

	def validate(self):
		self.set_missing_values()
		self.validate_dates()
		self.validate_customer()
		self.validate_fabric_item()
		self.validate_process_item()
		self.validate_design_items()
		self.validate_order_defaults()
		self.validate_wastage()
		self.calculate_totals()

		if self.docstatus == 1:
			self.set_existing_items_and_boms()

		self.set_item_creation_status()
		self.set_sales_order_status()
		self.set_fabric_transfer_status()
		self.set_production_packing_status()
		self.set_delivery_status()
		self.set_billing_status()
		self.set_status()

		self.set_title()

	def on_submit(self):
		self.set_order_defaults_for_customer()

	def on_cancel(self):
		if self.status == "Closed":
			frappe.throw(_("Closed Order cannot be cancelled. Re-open to cancel."))

		self.db_set("status", "Cancelled")

	def set_fabric_stock_qty(self):
		if not (self.fabric_item and self.source_warehouse):
			self.fabric_stock_qty = 0
			return

		bin_details = get_bin_details(self.fabric_item, self.source_warehouse)
		self.fabric_stock_qty = flt(bin_details.get("actual_qty"))

	def set_missing_values(self):
		self.attach_unlinked_item_images()
		self.set_design_details_from_image()
		self.set_fabric_item_details()
		self.set_process_item_details()

	def attach_unlinked_item_images(self):
		filters = {
			'attached_to_doctype': self.doctype,
			'attached_to_name': self.name
		}
		files_urls = frappe.db.get_all('File', filters, ['file_url'], order_by="creation", pluck="file_url")

		linked_images = {d.design_image for d in self.items}

		for file_url in files_urls:
			if file_url in linked_images:
				continue

			row = frappe.new_doc("Print Order Item")
			row.design_image = file_url
			row.design_gap = self.default_gap
			row.qty = self.default_qty
			row.uom = self.default_uom
			row.qty_type = self.default_qty_type
			row.per_wastage = self.default_wastage
			row.length_uom = self.default_length_uom
			self.append('items', row)

	def set_design_details_from_image(self):
		for d in self.items:
			if not d.design_image:
				continue
			if d.design_width and d.design_height:
				continue

			design_details = get_image_details(d.design_image)
			d.update(design_details)

	def set_fabric_item_details(self):
		details = get_fabric_item_details(self.fabric_item, get_default_process=False)
		for k, v in details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_process_item_details(self):
		details = get_process_item_details(self.process_item, get_default_paper=False)
		for k, v in details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_order_defaults_for_customer(self):
		customer_defaults = frappe.db.get_value("Customer", self.customer, default_fields_map.keys(), as_dict=1)
		if not customer_defaults:
			frappe.throw(_("Customer {0} not found").format(self.customer))

		if any(val for val in customer_defaults.values()):
			return

		new_values_to_update = {}
		for customer_fn, print_order_fn in default_fields_map.items():
			new_values_to_update[customer_fn] = self.get(print_order_fn)

		frappe.db.set_value("Customer", self.customer, new_values_to_update, notify=True)

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
				self.status = "To Confirm Order"
			elif self.production_status == "To Produce":
				self.status = "To Produce"
			elif self.delivery_status == "To Deliver":
				self.status = "To Deliver"
			elif self.billing_status == "To Bill":
				self.status = "To Bill"
			else:
				self.status = "Completed"

		else:
			self.status = "Cancelled"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)

	def update_status(self, status):
		self.set_status(status=status)
		self.set_fabric_transfer_status(update=True)
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_billing_status(update=True)
		self.set_status(update=True, status=status)
		self.notify_update()
		clear_doctype_notifications(self)

	def set_title(self):
		self.title = self.customer_name or self.customer

	def validate_order_defaults(self):
		validate_uom_and_qty_type(self)

	def validate_wastage(self):
		allowance = flt(frappe.db.get_single_value("Manufacturing Settings", "overproduction_percentage_for_work_order"))
		for d in self.items:
			if flt(d.per_wastage) > allowance:
				frappe.throw(_("Row #{0}: Wastage cannot be greater than Over Production Allowance of {1}").format(
					d.idx, frappe.bold(frappe.format(allowance, df=d.meta.get_field("per_wastage")))
				))

	def validate_dates(self):
		if self.delivery_date:
			if self.transaction_date and getdate(self.delivery_date) < getdate(self.transaction_date):
				frappe.throw(_("Planned Delivery Date cannot be before Order Date"))

			if self.po_date and getdate(self.delivery_date) < getdate(self.po_date):
				frappe.throw(_("Planned Delivery Date cannot be before Customer's Purchase Order Date"))

	def validate_customer(self):
		if self.get("customer"):
			validate_party_frozen_disabled("Customer", self.customer)

	def validate_fabric_item(self):
		if self.get("fabric_item"):
			validate_print_item(self.fabric_item, "Fabric")

			if not self.is_fabric_provided_by_customer:
				return

			item_details = frappe.get_cached_value("Item", self.fabric_item, ["is_customer_provided_item", "customer"], as_dict=1)

			if not item_details.is_customer_provided_item:
				frappe.throw(_("Fabric Item {0} is not a Customer Provided Item").format(frappe.bold(self.fabric_item)))

			if item_details.customer != self.customer:
				frappe.throw(_("Customer Provided Fabric Item {0} does not belong to Customer {1}").format(
					frappe.bold(self.fabric_item), frappe.bold(self.customer)))

	def validate_process_item(self):
		if self.get("process_item"):
			validate_print_item(self.process_item, "Print Process")

		for component_item_field, component_type in print_process_components.items():
			if self.get(f"{component_item_field}_required"):
				if self.get(component_item_field):
					validate_print_item(self.get(component_item_field), "Process Component", component_type)
			else:
				self.set(component_item_field, None)
				self.set(f"{component_item_field}_name", None)

		if self.docstatus == 1:
			if not self.get("process_item"):
				frappe.throw(_("Process Item is mandatory for submission"))

			process_doc = frappe.get_cached_doc("Item", self.process_item)
			for component_item_field in print_process_components:
				if process_doc.get(f"{component_item_field}_required") and not self.get(component_item_field):
					field_label = self.meta.get_label(component_item_field)
					frappe.throw(_("{0} is mandatory for submission").format(frappe.bold(field_label)))

	def validate_design_items(self):
		if self.docstatus == 1 and not self.items:
			frappe.throw(_("Design Items cannot be empty."))

		for d in self.items:
			if d.design_image and not (d.design_width or d.design_height):
				frappe.throw(_("Row #{0}: Image Dimensions cannot be empty").format(d.idx))

			if not d.qty:
				frappe.throw(_("Row #{0}: Qty cannot be 0").format(d.idx))

	def calculate_totals(self):
		self.total_print_length = 0
		self.total_fabric_length = 0
		self.total_panel_qty = 0

		conversion_factors = get_dp_conversion_factors()

		for d in self.items:
			validate_uom_and_qty_type(d)
			self.round_floats_in(d)

			d.panel_based_qty = cint(bool(d.design_gap))

			d.panel_length_inch = flt(d.design_height) + flt(d.design_gap)
			d.panel_length_meter = d.panel_length_inch * conversion_factors['inch_to_meter']
			d.panel_length_yard = d.panel_length_meter / conversion_factors['yard_to_meter']

			if d.uom != "Panel":
				d.length_uom = d.uom

			waste = d.per_wastage / 100
			uom_to_convert = d.length_uom + '_to_' + d.stock_uom
			conversion_factor = conversion_factors[uom_to_convert.lower()] or 1

			if d.uom != "Panel":
				if d.qty_type == "Print Qty":
					d.print_length = d.qty
					d.fabric_length = d.qty / (1 - waste) if waste < 1 else 0
				else:
					d.print_length = d.qty * (1 - waste) if waste < 1 else 0
					d.fabric_length = d.qty
			else:
				d.print_length = d.qty * d.panel_length_meter / conversion_factor
				d.fabric_length = d.print_length / (1 - waste) if waste < 1 else 0

			d.stock_print_length = d.print_length * conversion_factor
			d.stock_fabric_length = d.fabric_length * conversion_factor

			d.panel_qty = d.stock_print_length / d.panel_length_meter if d.panel_length_meter else 0
			d.panel_qty = flt(d.panel_qty, d.precision("panel_qty"))

			self.total_print_length += d.stock_print_length
			self.total_fabric_length += d.stock_fabric_length
			self.total_panel_qty += d.panel_qty

		self.total_print_length = flt(self.total_print_length, self.precision("total_print_length"))
		self.total_fabric_length = flt(self.total_fabric_length, self.precision("total_fabric_length"))
		self.total_panel_qty = flt(self.total_panel_qty, self.precision("total_panel_qty"))

	def set_existing_items_and_boms(self):
		for d in self.items:
			d.item_code = self.get_existing_design_item(d)
			d.item_name = frappe.get_cached_value("Item", d.item_code, "item_name") if d.item_code else None
			d.design_bom = self.get_existing_design_bom(d.item_code)

	def get_existing_design_item(self, row):
		filters = frappe._dict({
			"name": self.name,
			"customer": self.customer,
			"fabric_item": self.fabric_item,
			"design_image": row.design_image,
			"design_width": row.design_width,
			"design_height": row.design_height,
		})

		existing_design_item = frappe.db.sql_list("""
			SELECT i.item_code
			FROM `tabPrint Order Item` i
			INNER JOIN `tabPrint Order` p ON p.name = i.parent
			WHERE p.name != %(name)s AND ifnull(i.item_code, '') != ''
				AND p.customer = %(customer)s
				AND p.fabric_item = %(fabric_item)s
				AND i.design_image = %(design_image)s
				AND i.design_width = %(design_width)s
				AND i.design_height = %(design_height)s
			ORDER BY p.creation DESC
			LIMIT 1
		""", filters)

		return existing_design_item[0] if existing_design_item else None

	def get_existing_design_bom(self, item_code):
		if not item_code:
			return None

		filters = frappe._dict({
			"name": self.name,
			"item_code": item_code,
			"process_item": self.process_item,
		})

		process_conditions = ["p.process_item = %(process_item)s"]
		for component_item_field in print_process_components:
			if self.get(f"{component_item_field}_required"):
				process_conditions.append(f"p.{component_item_field}_required = 1")
				process_conditions.append(f"p.{component_item_field} = %({component_item_field})s")
			else:
				process_conditions.append(f"p.{component_item_field}_required = 0")

			filters[component_item_field] = self.get(component_item_field)

		process_conditions = f" AND {' AND '.join(process_conditions)}"

		existing_bom = frappe.db.sql_list("""
			SELECT i.design_bom
			FROM `tabPrint Order Item` i
			INNER JOIN `tabPrint Order` p ON p.name = i.parent
			WHERE p.name != %(name)s
				AND i.item_code = %(item_code)s
				AND ifnull(i.design_bom, '') != ''
				{0}
			ORDER BY p.creation DESC
			LIMIT 1
			""".format(process_conditions), filters)

		return existing_bom[0] if existing_bom else None

	def set_item_creation_status(self, update=False, update_modified=True):
		self.items_created = cint(all(d.item_code and d.design_bom for d in self.items))
		if update:
			self.db_set("items_created", self.items_created, update_modified=update_modified)

	def set_sales_order_status(self, update=False, update_modified=True):
		data = self.get_ordered_status_data()

		for d in self.items:
			d.ordered_qty = flt(data.ordered_qty_map.get(d.name))
			if update:
				d.db_set({
					'ordered_qty': d.ordered_qty
				}, update_modified=update_modified)

		self.per_ordered = flt(self.calculate_status_percentage('ordered_qty', 'stock_print_length', self.items))
		if update:
			self.db_set({
				'per_ordered': self.per_ordered
			}, update_modified=update_modified)

	def get_ordered_status_data(self):
		out = frappe._dict()
		out.ordered_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				ordered_data = frappe.db.sql("""
					SELECT i.print_order_item, i.stock_qty
					FROM `tabSales Order Item` i
					INNER JOIN `tabSales Order` s ON s.name = i.parent
					WHERE s.docstatus = 1 AND i.print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in ordered_data:
					out.ordered_qty_map.setdefault(d.print_order_item, 0)
					out.ordered_qty_map[d.print_order_item] += flt(d.stock_qty)

		return out

	def validate_ordered_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('ordered_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names)

	def set_fabric_transfer_status(self, update=False, update_modified=True):
		self.fabric_transfer_qty = self.get_fabric_transfer_qty()
		rounded_transfer_qty = flt(self.fabric_transfer_qty, self.precision("fabric_transfer_qty"))

		if self.status == "Closed" and rounded_transfer_qty <= 0:
			self.fabric_transfer_status = "Not Applicable"
		elif rounded_transfer_qty >= self.total_print_length or self.status == "Closed":
			self.fabric_transfer_status = "Transferred"
		else:
			self.fabric_transfer_status = "To Transfer"

		if update:
			self.db_set({
				'fabric_transfer_qty': self.fabric_transfer_qty,
				'fabric_transfer_status': self.fabric_transfer_status,
			}, update_modified=update_modified)

	def get_fabric_transfer_qty(self):
		out = 0

		if self.docstatus == 1:
			ste_data = frappe.db.sql("""
				select sum(IF(i.t_warehouse = %(wip_warehouse)s, i.transfer_qty, -1 * i.transfer_qty))
				from `tabStock Entry Detail` i
				inner join `tabStock Entry` ste on ste.name = i.parent
				where ste.docstatus = 1
					and ste.purpose in ('Material Transfer', 'Material Transfer for Manufacture')
					and ste.print_order = %(print_order)s
					and i.item_code = %(fabric_item)s
					and (i.t_warehouse = %(wip_warehouse)s or i.s_warehouse = %(wip_warehouse)s)
			""", {
				"print_order": self.name,
				"fabric_item": self.fabric_item,
				"wip_warehouse": self.wip_warehouse,
			})

			out = flt(ste_data[0][0]) if ste_data else 0

		return out

	def set_production_packing_status(self, update=False, update_modified=True):
		data = self.get_production_packing_data()

		for d in self.items:
			d.work_order_qty = flt(data.work_order_qty_map.get(d.name))
			d.produced_qty = flt(data.produced_qty_map.get(d.name))
			d.packed_qty = flt(data.packed_qty_map.get(d.name))

			if update:
				d.db_set({
					'work_order_qty': d.work_order_qty,
					'produced_qty': d.produced_qty,
					'packed_qty': d.packed_qty,
				}, update_modified=update_modified)

		self.per_work_ordered = flt(self.calculate_status_percentage('work_order_qty', 'stock_print_length', self.items))
		self.per_produced = flt(self.calculate_status_percentage('produced_qty', 'stock_print_length', self.items))
		self.per_packed = flt(self.calculate_status_percentage('packed_qty', 'stock_print_length', self.items))

		production_within_allowance = self.per_work_ordered >= 100 and self.per_produced > 0 and not data.has_incomplete_work_order
		self.production_status = self.get_completion_status('per_produced', 'Produce',
			not_applicable=self.status == "Closed", within_allowance=production_within_allowance)

		packing_within_allowance = self.per_ordered >= 100 and self.per_packed > 0 and not data.has_incomplete_packing
		self.packing_status = self.get_completion_status('per_packed', 'Pack',
			not_applicable=self.status == "Closed" or not self.packing_slip_required,
			within_allowance=packing_within_allowance)

		if update:
			self.db_set({
				'per_work_ordered': self.per_work_ordered,
				'per_produced': self.per_produced,
				'per_packed': self.per_packed,

				'production_status': self.production_status,
				'packing_status': self.packing_status,
			}, update_modified=update_modified)

	def get_production_packing_data(self):
		out = frappe._dict()
		out.work_order_qty_map = {}
		out.produced_qty_map = {}
		out.packed_qty_map = {}
		out.has_incomplete_packing = False
		out.has_incomplete_work_order = False

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				# Work Order
				work_order_data = frappe.db.sql("""
					SELECT print_order_item, qty, produced_qty, production_status
					FROM `tabWork Order`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in work_order_data:
					out.work_order_qty_map.setdefault(d.print_order_item, 0)
					out.work_order_qty_map[d.print_order_item] += flt(d.qty)

					out.produced_qty_map.setdefault(d.print_order_item, 0)
					out.produced_qty_map[d.print_order_item] += flt(d.produced_qty)

					if d.production_status != "Produced":
						out.has_incomplete_work_order = True

				# Packing Slips
				packed_data = frappe.db.sql("""
					SELECT print_order_item, stock_qty
					FROM `tabPacking Slip Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in packed_data:
					out.packed_qty_map.setdefault(d.print_order_item, 0)
					out.packed_qty_map[d.print_order_item] += flt(d.stock_qty)

			# Unpacked Sales Orders
			sales_orders_to_pack = frappe.db.sql_list("""
				select count(so.name)
				from `tabSales Order Item` i
				inner join `tabSales Order` so on so.name = i.parent
				where so.docstatus = 1 and so.packing_status = 'To Pack' and i.print_order = %s
			""", self.name)
			sales_orders_to_pack = cint(sales_orders_to_pack[0]) if sales_orders_to_pack else 0
			if sales_orders_to_pack:
				out.has_incomplete_packing = True

		return out

	def validate_work_order_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('work_order_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

	def validate_produced_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('produced_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="max_qty_field", max_qty_field="stock_fabric_length")

	def validate_packed_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('packed_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

	def set_delivery_status(self, update=False, update_modified=True):
		data = self.get_delivered_status_data()

		for d in self.items:
			d.delivered_qty = flt(data.delivered_qty_map.get(d.name))
			if update:
				d.db_set({
					'delivered_qty': d.delivered_qty
				}, update_modified=update_modified)

		self.per_delivered = flt(self.calculate_status_percentage('delivered_qty', 'stock_print_length', self.items))
		within_allowance = self.per_ordered >= 100 and self.per_delivered > 0 and not data.has_incomplete_delivery

		self.delivery_status = self.get_completion_status('per_delivered', 'Deliver',
			not_applicable=self.status == "Closed", within_allowance=within_allowance)

		if update:
			self.db_set({
				'per_delivered': self.per_delivered,
				'delivery_status': self.delivery_status,
			}, update_modified=update_modified)

	def get_delivered_status_data(self):
		out = frappe._dict()
		out.delivered_qty_map = {}
		out.has_incomplete_delivery = False

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				delivered_data = frappe.db.sql("""
					SELECT print_order_item, stock_qty
					FROM `tabDelivery Note Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in delivered_data:
					out.delivered_qty_map.setdefault(d.print_order_item, 0)
					out.delivered_qty_map[d.print_order_item] += flt(d.stock_qty)

			sales_orders_to_deliver = frappe.db.sql_list("""
				select count(so.name)
				from `tabSales Order Item` i
				inner join `tabSales Order` so on so.name = i.parent
				where so.docstatus = 1 and so.delivery_status = 'To Deliver' and i.print_order = %s
			""", self.name)
			sales_orders_to_deliver = cint(sales_orders_to_deliver[0]) if sales_orders_to_deliver else 0
			if sales_orders_to_deliver:
				out.has_incomplete_delivery = True

		return out

	def validate_delivered_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('delivered_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="qty")

	def set_billing_status(self, update=False, update_modified=True):
		data = self.get_billed_status_data()

		for d in self.items:
			d.billed_qty = flt(data.billed_qty_map.get(d.name))
			if update:
				d.db_set({
					'billed_qty': d.billed_qty
				}, update_modified=update_modified)

		self.per_billed = flt(self.calculate_status_percentage('billed_qty', 'stock_print_length', self.items))
		within_allowance = self.per_ordered >= 100 and self.per_billed > 0 and not data.has_incomplete_billing

		self.billing_status = self.get_completion_status('per_billed', 'Bill',
			not_applicable=self.status == "Closed", within_allowance=within_allowance)

		if update:
			self.db_set({
				'per_billed': self.per_billed,
				'billing_status': self.billing_status,
			}, update_modified=update_modified)

	def get_billed_status_data(self):
		out = frappe._dict()
		out.billed_qty_map = {}
		out.has_incomplete_billing = False

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				billed_data = frappe.db.sql("""
					SELECT print_order_item, stock_qty
					FROM `tabSales Invoice Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in billed_data:
					out.billed_qty_map.setdefault(d.print_order_item, 0)
					out.billed_qty_map[d.print_order_item] += flt(d.stock_qty)

			sales_orders_to_bill = frappe.db.sql_list("""
				select count(so.name)
				from `tabSales Order Item` i
				inner join `tabSales Order` so on so.name = i.parent
				where so.docstatus = 1 and so.billing_status = 'To Bill' and i.print_order = %s
			""", self.name)
			sales_orders_to_bill = cint(sales_orders_to_bill[0]) if sales_orders_to_bill else 0
			if sales_orders_to_bill:
				out.has_incomplete_billing = True

		return out

	def validate_billed_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('billed_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="max_qty_field", max_qty_field="stock_fabric_length")

	def _start_print_order(self, fabric_transfer_qty, publish_progress=False):
		frappe.flags.skip_print_order_status_update = True

		# Design Items
		if not all(d.item_code and d.design_bom for d in self.items):
			self._create_design_items_and_boms(publish_progress=publish_progress, ignore_version=True, ignore_feed=True)

		# Fabric Transfer
		if flt(fabric_transfer_qty) > 0:
			if publish_progress:
				publish_print_order_progress(self.name, "Transferring Fabric", 0, 1)

			stock_entry = make_fabric_transfer_entry(self, fabric_transfer_qty, for_submit=True)
			stock_entry.flags.ignore_version = True
			stock_entry.flags.ignore_feed = True
			stock_entry.save()
			stock_entry.submit()

			stock_entry_row = stock_entry.items[0]

			fabric_transfer_msg = _("Fabric Transferred to Work in Progress Warehouse ({0} {1}): {2}").format(
				stock_entry_row.get_formatted("qty"),
				stock_entry_row.uom,
				frappe.utils.get_link_to_form("Stock Entry", stock_entry.name)
			)
			frappe.msgprint(fabric_transfer_msg)

			if publish_progress:
				publish_print_order_progress(self.name, "Transferring Fabric", 1, 1)

		# Sales Order
		if flt(self.per_ordered) < 100:
			if publish_progress:
				publish_print_order_progress(self.name, "Creating Sales Order", 0, 1)

			sales_order = make_sales_order(self.name)
			sales_order.flags.ignore_version = True
			sales_order.flags.ignore_feed = True
			sales_order.save()
			sales_order.submit()

			sales_order_msg = _("Sales Order created: {0}").format(
				frappe.utils.get_link_to_form("Sales Order", sales_order.name)
			)
			frappe.msgprint(sales_order_msg)

			if publish_progress:
				publish_print_order_progress(self.name, "Creating Sales Order", 1, 1)

		# Work Orders
		if flt(self.per_work_ordered) < 100:
			create_work_orders(self.name, publish_progress=publish_progress, ignore_version=True, ignore_feed=True)

		# Status Update
		frappe.flags.skip_print_order_status_update = False

		self.set_item_creation_status(update=True)
		self.set_fabric_transfer_status(update=True)
		self.set_sales_order_status(update=True)
		self.set_production_packing_status(update=True)
		self.set_status(update=True)

		self.validate_ordered_qty()
		self.validate_work_order_qty()

		self.notify_update()

	def _create_design_items_and_boms(self, publish_progress=False, ignore_version=True, ignore_feed=True):
		for i, d in enumerate(self.items):
			if not d.item_code:
				item_doc = make_design_item(d, self.fabric_item, self.customer)
				item_doc.flags.ignore_version = ignore_version
				item_doc.flags.ignore_feed = ignore_feed
				item_doc.save()

				d.db_set({
					"item_code": item_doc.name,
					"item_name": item_doc.item_name
				})

			if not d.design_bom:
				components = []
				for component_item_field in print_process_components:
					if self.get(f"{component_item_field}_required"):
						components.append(self.get(component_item_field))

				bom_doc = make_design_bom(d.item_code, self.fabric_item, self.process_item, components=components)
				bom_doc.flags.ignore_version = ignore_version
				bom_doc.flags.ignore_feed = ignore_feed
				bom_doc.save()
				bom_doc.submit()

				d.db_set("design_bom", bom_doc.name)

			if publish_progress:
				publish_print_order_progress(self.name, "Creating Design Items and BOMs", i + 1, len(self.items))

		if not frappe.flags.skip_print_order_status_update:
			self.set_item_creation_status(update=True)
			self.notify_update()

		frappe.msgprint(_("Design Items and BOMs created successfully."))


def update_conversion_factor_global_defaults():
	from erpnext.setup.doctype.uom_conversion_factor.uom_conversion_factor import get_uom_conv_factor
	inch_to_meter = get_uom_conv_factor("Inch", "Meter")
	yard_to_meter = get_uom_conv_factor("Yard", "Meter")

	frappe.db.set_default("inch_to_meter", inch_to_meter)
	frappe.db.set_default("yard_to_meter", yard_to_meter)


def get_yard_to_meter():
	return get_dp_conversion_factors()["yard_to_meter"]


def get_dp_conversion_factors():
	return {
		"inch_to_meter": flt(frappe.db.get_default("inch_to_meter")) or 0.0254,
		"yard_to_meter": flt(frappe.db.get_default("yard_to_meter")) or 0.9144,
		"meter_to_meter": 1
	}


def validate_print_item(item_code, print_item_type, print_process_component=None):
	item = frappe.get_cached_doc("Item", item_code)

	if print_item_type:
		if item.print_item_type != print_item_type:
			frappe.throw(_("{0} is not a {1} Item").format(frappe.bold(item_code), print_item_type))

		if print_item_type == "Process Component" and print_process_component:
			if item.print_process_component != print_process_component:
				frappe.throw(_("{0} is not a {1} Component Item").format(frappe.bold(item_code), print_process_component))

	from erpnext.stock.doctype.item.item import validate_end_of_life
	validate_end_of_life(item.name, item.end_of_life, item.disabled)


def validate_uom_and_qty_type(doc):
	fn_map = frappe._dict()

	if doc.doctype == "Print Order":
		fn_map.uom_fn = 'default_uom'
		fn_map.length_uom_fn = 'default_length_uom'
		fn_map.qty_type_fn = 'default_qty_type'

	elif doc.doctype == "Print Order Item":
		fn_map.uom_fn = 'uom'
		fn_map.length_uom_fn = 'length_uom'
		fn_map.qty_type_fn = 'qty_type'

	else:
		fn_map.uom_fn = 'default_printing_uom'
		fn_map.length_uom_fn = 'default_printing_length_uom'
		fn_map.qty_type_fn = 'default_printing_qty_type'

	if doc.get(fn_map.uom_fn) == "Panel":
		doc.set(fn_map.qty_type_fn, "Print Qty")
	else:
		doc.set(fn_map.length_uom_fn, doc.get(fn_map.uom_fn))


@frappe.whitelist()
def get_order_defaults_from_customer(customer):
	customer_defaults = frappe.db.get_value("Customer", customer, default_fields_map.keys(), as_dict=1)
	if not customer_defaults:
		frappe.throw(_("Customer {0} not found").format(customer))

	customer_order_defaults = {}
	for customer_fn, print_order_fn in default_fields_map.items():
		if customer_defaults.get(customer_fn):
			customer_order_defaults[print_order_fn] = customer_defaults[customer_fn]

	return customer_order_defaults


@frappe.whitelist()
def update_status(print_order, status):
	if not frappe.has_permission("Print Order", "submit"):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	doc = frappe.get_doc("Print Order", print_order)

	if doc.docstatus != 1:
		return
	if status == "Closed" and doc.per_ordered == 100:
		return

	doc.run_method("update_status", status)


@frappe.whitelist()
def close_or_unclose_print_orders(names, status):
	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		update_status(name, status)


def check_print_order_is_closed(doc):
	if cint(doc.get("is_return")):
		return

	for d in doc.get("items"):
		if d.get("print_order"):
			status = frappe.db.get_value("Print Order", d.print_order, "status", cache=True)
			if status == "Closed":
				frappe.throw(_("Row #{0}: {1} is {2}").format(
					d.idx, frappe.get_desk_link("Print Order", d.print_order), status))


@frappe.whitelist()
def start_print_order(print_order, fabric_transfer_qty=None):
	from erpnext.stock.stock_ledger import get_allow_negative_stock

	doc = frappe.get_doc('Print Order', print_order)

	if doc.docstatus != 1:
		frappe.throw(_("Print Order {0} is not submitted").format(doc.name))
	if doc.status == "Closed":
		frappe.throw(_("Print Order {0} is Closed").format(doc.name))

	if fabric_transfer_qty is None:
		fabric_transfer_qty = max(doc.total_fabric_length - doc.fabric_transfer_qty, 0)

	fabric_transfer_qty = flt(fabric_transfer_qty, precision=doc.precision("total_fabric_length"))

	doc.set_fabric_stock_qty()
	if fabric_transfer_qty > 0 and fabric_transfer_qty > doc.fabric_stock_qty and not get_allow_negative_stock():
		frappe.throw(_("Not enough Fabric Item {0} in Raw Material Warehouse ({1} Meter in stock)").format(
			frappe.utils.get_link_to_form("Item", doc.fabric_item), doc.get_formatted("fabric_stock_qty")
		))

	if len(doc.items) > 5:
		doc.queue_action("_start_print_order", fabric_transfer_qty=fabric_transfer_qty, publish_progress=True, timeout=1800)
		frappe.msgprint(_("Starting Print Order in background..."), alert=True)
	else:
		doc._start_print_order(fabric_transfer_qty=fabric_transfer_qty, publish_progress=True)


@frappe.whitelist()
def create_design_items_and_boms(print_order):
	if isinstance(print_order, str):
		doc = frappe.get_doc('Print Order', print_order)
	else:
		doc = print_order

	if doc.docstatus != 1:
		frappe.throw(_("Submit the Print Order first."))

	if all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Printed Design Items and BOMs already created."))

	if len(doc.items) > 5:
		doc.queue_action("_create_design_items_and_boms", publish_progress=True, timeout=600)
		frappe.msgprint(_("Creating Design Items and BOMs..."), alert=True)
	else:
		doc._create_design_items_and_boms(publish_progress=True)


def make_design_item(design_item_row, fabric_item, customer):
	if not design_item_row:
		frappe.throw(_('Print Order Row is mandatory.'))
	if not fabric_item:
		frappe.throw(_('Fabric Item is mandatory.'))

	default_item_group = frappe.db.get_single_value("Digital Printing Settings", "default_item_group_for_printed_design_item")

	if not default_item_group:
		frappe.throw(_("Select Default Item Group for Printed Design Item in Digital Printing Settings."))

	item_doc = frappe.new_doc("Item")
	if item_doc.item_naming_by == "Item Code":
		item_doc.item_naming_by = "Naming Series"

	item_doc.update({
		"item_group": default_item_group,
		"print_item_type": "Printed Design",
		"item_name": design_item_row.design_name,
		"stock_uom": design_item_row.stock_uom,
		"sales_uom": design_item_row.uom,
		"fabric_item": fabric_item,
		"image": design_item_row.design_image,
		"design_width": design_item_row.design_width,
		"design_height": design_item_row.design_height,
		"design_gap": design_item_row.design_gap,
		"per_wastage": design_item_row.per_wastage,
		"design_notes": design_item_row.design_notes,
		"customer": customer,
	})

	item_doc.append("uom_conversion_graph", {
		"from_uom": "Panel",
		"from_qty": 1,
		"to_uom": "Meter",
		"to_qty": design_item_row.panel_length_meter
	})

	return item_doc


def make_design_bom(design_item, fabric_item, process_item, components=None):
	def validate_convertible_to_meter(item_code):
		conversion = get_conversion_factor(item_code, "Meter")
		if conversion.get("not_convertible"):
			frappe.throw(_("Could not create BOM for Design Item {0} because {1} is not convertible to Meter").format(
				frappe.bold(design_item), frappe.get_desk_link("Item", item_code)
			))

	if not design_item:
		frappe.throw(_('Design Item is mandatory.'))
	if not fabric_item:
		frappe.throw(_('Fabric Item is mandatory.'))
	if not process_item:
		frappe.throw(_('Process Item is mandatory.'))

	if not components:
		components = []

	bom_doc = frappe.new_doc("BOM")
	bom_doc.update({
		"item": design_item,
		"quantity": 1,
	})

	validate_convertible_to_meter(fabric_item)
	validate_convertible_to_meter(process_item)

	bom_doc.append("items", {
		"item_code": fabric_item,
		"qty": 1,
		"uom": "Meter",
		"skip_transfer_for_manufacture": 0,
	})
	bom_doc.append("items", {
		"item_code": process_item,
		"qty": 1,
		"uom": "Meter",
		"skip_transfer_for_manufacture": 1,
	})

	for component_item in components:
		validate_convertible_to_meter(component_item)

		bom_doc.append("items", {
			"item_code": component_item,
			"qty": 1,
			"uom": "Meter",
			"skip_transfer_for_manufacture": 1,
		})

	return bom_doc


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_payment_schedule")

	def item_condition(source, source_parent, target_parent):
		if not source.item_code:
			return False

		if source.name in [d.print_order_item for d in target_parent.get('items') if d.print_order_item]:
			return False

		return abs(source.ordered_qty) < abs(source.print_length)

	def update_item(source, target, source_parent, target_parent):
		target.qty = flt(source.print_length) - flt(source.ordered_qty)

	doc = get_mapped_doc("Print Order", source_name, {
		"Print Order": {
			"doctype": "Sales Order",
			"field_map": {
				"delivery_date": "delivery_date",
				"fg_warehouse": "set_warehouse",
			},
			"validation": {
				"docstatus": ["=", 1],
			}
		},
		"Print Order Item": {
			"doctype": "Sales Order Item",
			"field_map": {
				"name": "print_order_item",
				"parent": "print_order",
				"bom": "bom",
				"item_code": "item_code",
				"design_name": "item_name",
				"print_length": "qty",
				"length_uom": "uom",
				"panel_length_meter": "panel_length_meter",
				"panel_based_qty": "panel_based_qty",
			},
			"postprocess": update_item,
			"condition": item_condition,
		}
	}, target_doc, set_missing_values)

	return doc


@frappe.whitelist()
def create_work_orders(print_order, publish_progress=False, ignore_version=True, ignore_feed=True):
	from erpnext.selling.doctype.sales_order.sales_order import make_work_orders

	if isinstance(print_order, str):
		doc = frappe.get_doc('Print Order', print_order)
	else:
		doc = print_order

	if doc.docstatus != 1:
		frappe.throw(_("Submit the Print Order first."))

	if not all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Create Items and BOMs first"))

	sales_orders = frappe.get_all("Sales Order Item", 'distinct parent as sales_order', {
		'print_order': doc.name,
		'docstatus': 1
	}, pluck="sales_order")

	wo_items = []

	for so in sales_orders:
		so_doc = frappe.get_doc('Sales Order', so)
		wo_items += so_doc.get_work_order_items()

	wo_list = []
	for i, d in enumerate(wo_items):
		wo_list += make_work_orders([d], so_doc.company, ignore_version=ignore_version, ignore_feed=ignore_feed)

		if publish_progress:
			publish_print_order_progress(doc.name, "Creating Work Orders", i+1, len(wo_items))

	if wo_list:
		wo_message = _("Work Orders created: {0}").format(
			", ".join([frappe.utils.get_link_to_form('Work Order', wo) for wo in wo_list])
		)
		frappe.msgprint(wo_message, indicator='green')
	else:
		frappe.msgprint(_("Work Orders already created"))


@frappe.whitelist()
def make_fabric_transfer_entry(print_order, fabric_transfer_qty=None, for_submit=False):
	if isinstance(print_order, str):
		doc = frappe.get_doc('Print Order', print_order)
	else:
		doc = print_order

	if not all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Create Items and BOMs first"))

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.purpose = "Material Transfer for Manufacture"
	stock_entry.print_order = doc.name
	stock_entry.company = doc.company
	stock_entry.from_warehouse = doc.source_warehouse
	stock_entry.to_warehouse = doc.wip_warehouse

	row = stock_entry.append("items")
	row.item_code = doc.fabric_item
	row.s_warehouse = stock_entry.from_warehouse
	row.t_warehouse = stock_entry.to_warehouse

	if fabric_transfer_qty is None:
		fabric_transfer_qty = max(flt(doc.total_fabric_length) - flt(doc.fabric_transfer_qty), 0)

	fabric_transfer_qty = flt(fabric_transfer_qty)

	row.qty = fabric_transfer_qty
	row.uom = "Meter"

	stock_entry.set_stock_entry_type()

	if not for_submit:
		stock_entry.run_method("set_missing_values")
		stock_entry.run_method("set_actual_qty")
		stock_entry.run_method("calculate_rate_and_amount", raise_error_if_no_rate=False)

	return stock_entry


@frappe.whitelist()
def make_packing_slip_for_items(source, target_doc=None):
	if isinstance(source, str):
		source = json.loads(source)

	for print_order, selected_rows in source.items():
		if selected_rows:
			target_doc = make_packing_slip(print_order, target_doc, selected_rows=selected_rows)

	return target_doc


@frappe.whitelist()
def make_packing_slip(source_name, target_doc=None, selected_rows=None):
	from erpnext.selling.doctype.sales_order.sales_order import make_packing_slip

	doc = frappe.get_doc("Print Order", source_name)

	if selected_rows and isinstance(selected_rows, str):
		selected_rows = json.loads(selected_rows)

	if selected_rows:
		selected_children = frappe.get_all("Sales Order Item", filters={"print_order_item": ["in", selected_rows]}, pluck="name")
		frappe.flags.selected_children = {"items": selected_children}

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.company = %(company)s AND i.print_order = %(print_order)s
	""", {"print_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be packed"))

	for d in sales_orders:
		target_doc = make_packing_slip(d.name, target_doc=target_doc)

	return target_doc


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note_from_packing_slips

	doc = frappe.get_doc("Print Order", source_name)

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.per_delivered < 100 AND s.skip_delivery_note = 0
			AND s.company = %(company)s AND i.print_order = %(print_order)s
	""", {"print_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be delivered"))

	packing_filter = "Packed Items Only" if doc.packing_slip_required else None

	for d in sales_orders:
		target_doc = make_delivery_note_from_packing_slips(d.name, target_doc=target_doc, packing_filter=packing_filter)

	return target_doc


@frappe.whitelist()
def make_sales_invoice(print_order):
	from erpnext.controllers.queries import _get_delivery_notes_to_be_billed
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	doc = frappe.get_doc("Print Order", print_order)

	target_doc = frappe.new_doc("Sales Invoice")

	delivery_note_filters = ["""EXISTS(
		SELECT dni.name
		FROM `tabDelivery Note Item` dni
		WHERE dni.parent = `tabDelivery Note`.name
			AND dni.print_order = {0}
	)""".format(frappe.db.escape(doc.name))]

	delivery_notes = _get_delivery_notes_to_be_billed(filters=delivery_note_filters)

	if not delivery_notes:
		frappe.throw(_("There are no Delivery Notes to be billed"))

	for d in delivery_notes:
		target_doc = make_sales_invoice(d.name, target_doc=target_doc)

	return target_doc


@frappe.whitelist()
def make_customer_fabric_stock_entry(source_name, target_doc=None):
	po_doc = frappe.get_doc('Print Order', source_name)

	if po_doc.docstatus != 1:
		frappe.throw(_("Print Order {0} is not submitted").format(po_doc.name))

	if not target_doc:
		target_doc = frappe.new_doc("Stock Entry")

	if isinstance(target_doc, str):
		target_doc = frappe.get_doc(json.loads(target_doc))

	target_doc.append("items", {
		"item_code": po_doc.fabric_item,
		"qty": po_doc.total_fabric_length,
		"uom": "Meter",
	})

	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_rate_and_amount")

	return target_doc


@frappe.whitelist()
def get_image_details(image_url):
	doc_name = frappe.get_value('File', filters={'file_url': image_url})

	if not doc_name:
		frappe.throw(_("File {0} not found").format(image_url))

	file_doc = frappe.get_doc("File", doc_name)
	file_name = file_doc.get("original_file_name") or file_doc.file_name

	out = frappe._dict()
	out.design_name = ".".join(file_name.split('.')[:-1]) or file_name

	im = Image.open(file_doc.get_full_path())
	out.design_width = flt(im.size[0] / 10, 1)
	out.design_height = flt(im.size[1] / 10, 1)

	return out


@frappe.whitelist()
def get_fabric_item_details(fabric_item, get_default_process=True):
	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()

	out = frappe._dict()
	out.fabric_item_name = fabric_doc.item_name
	out.fabric_material = fabric_doc.fabric_material
	out.fabric_type = fabric_doc.fabric_type
	out.fabric_width = fabric_doc.fabric_width
	out.fabric_gsm = fabric_doc.fabric_gsm

	if fabric_item and cint(get_default_process):
		process_details = get_default_fabric_process(fabric_item)
		out.update(process_details)

	return out


@frappe.whitelist()
def get_default_fabric_process(fabric_item):
	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()
	out = frappe._dict()

	# Set process values as None to unset in UI
	out.process_item = None
	out.process_item_name = None

	for component_item_field in print_process_components:
		out[component_item_field] = None
		out[f"{component_item_field}_name"] = None
		out[f"{component_item_field}_required"] = 0

	# Set process and component from rules
	print_process_defaults = get_print_process_values(fabric_doc.name)
	out.update(print_process_defaults)

	process_details = get_process_item_details(out.process_item, fabric_doc.name, get_default_paper=True)
	out.update(process_details)

	return out


@frappe.whitelist()
def get_process_item_details(process_item, fabric_item=None, get_default_paper=True):
	process_doc = frappe.get_cached_doc("Item", process_item) if process_item else frappe._dict()

	out = frappe._dict()
	out.process_item_name = process_doc.item_name

	for component_item_field in print_process_components:
		out[f"{component_item_field}_required"] = process_doc.get(f"{component_item_field}_required")

	if fabric_item and process_item and get_default_paper:
		out.update(get_default_paper_items(fabric_item, process_item))

	return out


@frappe.whitelist()
def get_default_paper_items(fabric_item, process_item):
	if not fabric_item:
		frappe.throw(_("Fabric Item not provided"))
	if not process_item:
		frappe.throw(_("Process Item not provided"))

	fabric_doc = frappe.get_cached_doc("Item", fabric_item)
	process_doc = frappe.get_cached_doc("Item", process_item)

	out = frappe._dict()

	# Default Sublimation Paper
	if process_doc.sublimation_paper_item_required:
		sublimation_papers = get_applicable_papers("Sublimation Paper", fabric_doc.fabric_width)
		if len(sublimation_papers) == 1:
			out.sublimation_paper_item = sublimation_papers[0].name
			out.sublimation_paper_item_name = sublimation_papers[0].item_name

	# Default Protection Paper
	if process_doc.protection_paper_item_required:
		protection_papers = get_applicable_papers("Protection Paper", fabric_doc.fabric_width)
		if len(protection_papers) == 1:
			out.protection_paper_item = protection_papers[0].name
			out.protection_paper_item_name = protection_papers[0].item_name

	return out


def publish_print_order_progress(print_order, title, progress, total, description=None):
	progress_data = {
		"print_order": print_order,
		"title": title,
		"progress": progress,
		"total": total,
		"description": description,
	}

	frappe.publish_realtime("print_order_progress", progress_data, doctype="Print Order", docname=print_order)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_print_orders_to_be_delivered(doctype, txt, searchfield, start, page_len, filters, as_dict):
	return _get_print_orders_to_be_delivered(doctype, txt, searchfield, start, page_len, filters, as_dict)


def _get_print_orders_to_be_delivered(doctype="Print Order", txt="", searchfield="name", start=0, page_len=0,
		filters=None, as_dict=True, ignore_permissions=False):
	from frappe.desk.reportview import get_match_cond, get_filters_cond
	from erpnext.controllers.queries import get_fields

	fields = get_fields("Print Order")
	select_fields = ", ".join(["`tabPrint Order`.{0}".format(f) for f in fields])
	limit = "limit {0}, {1}".format(start, page_len) if page_len else ""

	if not filters:
		filters = {}

	return frappe.db.sql("""
		select {fields}
		from `tabPrint Order`
		where `tabPrint Order`.docstatus = 1
			and `tabPrint Order`.`status` != 'Closed'
			and `tabPrint Order`.`items_created` = 1
			and `tabPrint Order`.`delivery_status` = 'To Deliver'
			and `tabPrint Order`.`{key}` like {txt}
			and `tabPrint Order`.`per_delivered` < `tabPrint Order`.`per_produced`
			and (`tabPrint Order`.`packing_slip_required` = 0 or `tabPrint Order`.`per_delivered` < `tabPrint Order`.`per_packed`)
			{fcond} {mcond}
		order by `tabPrint Order`.transaction_date, `tabPrint Order`.creation
		{limit}
	""".format(
		fields=select_fields,
		key=searchfield,
		fcond=get_filters_cond(doctype, filters, [], ignore_permissions=ignore_permissions),
		mcond="" if ignore_permissions else get_match_cond(doctype),
		limit=limit,
		txt="%(txt)s",
	), {"txt": ("%%%s%%" % txt)}, as_dict=as_dict)
