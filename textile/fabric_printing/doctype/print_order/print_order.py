# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint, round_up
from frappe.model.mapper import get_mapped_doc
from frappe.desk.notifications import clear_doctype_notifications
from textile.fabric_printing.doctype.print_process_rule.print_process_rule import get_print_process_values, get_applicable_papers
from textile.utils import validate_textile_item, get_textile_conversion_factors, printing_components
from textile.controllers.textile_order import TextileOrder
from PIL import Image
import json


default_fields_map = {
	"default_printing_uom": "default_uom",
	"default_printing_gap": "default_gap",
	"default_printing_qty_type": "default_qty_type",
	"default_printing_length_uom": "default_length_uom"
}

force_customer_fields = ["customer_name"]
force_fabric_fields = ["fabric_item_name", "fabric_material", "fabric_type", "fabric_width", "fabric_gsm", "fabric_per_pickup"]
force_process_fields = (
	["process_item_name"]
	+ [f"{component_item_field}_required" for component_item_field in printing_components]
	+ [f"{component_item_field}_separate_process" for component_item_field in printing_components]
)
force_process_component_fields = (
	[f"{component_item_field}_name" for component_item_field in printing_components]
	+ [f"{component_item_field}_by_fabric_weight" for component_item_field in printing_components]
)

force_fields = force_customer_fields + force_fabric_fields + force_process_fields + force_process_component_fields


class PrintOrder(TextileOrder):
	@property
	def fabric_stock_qty(self):
		return self.get_fabric_stock_qty(self.fabric_item, self.fabric_warehouse)

	def get_feed(self):
		if self.get("title"):
			return self.title

	def onload(self):
		if self.docstatus == 0:
			self.set_missing_values()
			self.calculate_totals()

	@frappe.whitelist()
	def on_upload_complete(self):
		self.set_missing_values()
		self.calculate_totals()

	def validate(self):
		self.set_missing_values()
		self.set_values_for_coated_fabric()
		self.validate_dates()
		self.validate_customer()
		self.validate_pretreatment_order()
		self.validate_fabric_item("Ready Fabric")
		self.validate_process_items()
		self.validate_design_items()
		self.validate_order_defaults()
		self.validate_wastage()
		self.clean_remarks()
		self.calculate_totals()

		if self.docstatus == 1:
			self.set_existing_items_and_boms()

		self.set_item_creation_status()
		self.set_sales_order_status()
		self.set_fabric_transfer_status()
		self.set_production_packing_status()
		self.set_delivery_status()
		self.set_status()

		self.set_title(self.fabric_material, self.total_print_length)

	def before_update_after_submit(self):
		self.validate_dates()

	def on_submit(self):
		self.set_order_defaults_for_customer()

	def on_cancel(self):
		if self.status == "Closed":
			frappe.throw(_("Closed Order cannot be cancelled. Re-open to cancel."))

		self.update_status_on_cancel()

	def set_missing_values(self, get_default_process=False):
		self.set_default_cost_center()
		self.attach_unlinked_item_images()
		self.set_design_details_from_image()
		self.set_fabric_item_details(get_default_process=get_default_process)
		self.set_process_item_details()
		self.set_process_component_details()

	def set_default_cost_center(self):
		if not self.get("cost_center"):
			self.cost_center = frappe.db.get_single_value("Fabric Printing Settings",
			"default_printing_cost_center")

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

			design_details = get_image_details(d.design_image, throw_not_found=self.docstatus == 1)
			d.update(design_details)

	def set_fabric_item_details(self, get_default_process=False):
		details = get_fabric_item_details(self.fabric_item, get_default_process=get_default_process)
		for k, v in details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_process_item_details(self):
		details = get_process_item_details(self.process_item, get_default_paper=False)
		for k, v in details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_process_component_details(self):
		for component_item_field in printing_components:
			if not self.get(f"{component_item_field}_required"):
				self.set(component_item_field, None)

			component_item_code = self.get(component_item_field)
			details = get_process_component_details(component_item_code, component_item_field)
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

	def set_values_for_coated_fabric(self):
		self.skip_transfer = cint(self.coating_item_separate_process)

		coated_fabric_warehouse = frappe.db.get_single_value("Fabric Printing Settings", "default_coating_fg_warehouse")
		if self.coating_item_separate_process and coated_fabric_warehouse:
			self.fabric_warehouse = coated_fabric_warehouse

	def update_status_on_cancel(self):
		self.db_set({
			"status": "Cancelled",
			"fabric_transfer_status": "Not Applicable",
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
		self.set_fabric_transfer_status(update=True)
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_status(update=True, status=status)
		self.notify_update()
		clear_doctype_notifications(self)

	def close_linked_documents(self):
		from erpnext.manufacturing.doctype.work_order.work_order import stop_unstop
		from erpnext.selling.doctype.sales_order.sales_order import update_status as update_sales_order_status

		work_orders = frappe.get_all("Work Order", filters={
			"print_order": self.name,
			"docstatus": 1,
			"status": ["not in", ("Stopped", "Completed")]
		}, pluck="name")

		for name in work_orders:
			stop_unstop(name, "Stopped")

		sales_orders = frappe.db.sql_list("""
			select distinct so.name
			from `tabSales Order` so
			inner join `tabSales Order Item` i on i.parent = so.name
			where so.docstatus = 1 and i.print_order = %s and so.status != 'Closed' and so.delivery_status = 'To Deliver'
		""", self.name)

		for name in sales_orders:
			update_sales_order_status("Closed", name)

	def reopen_linked_documents(self):
		from erpnext.manufacturing.doctype.work_order.work_order import stop_unstop
		from erpnext.selling.doctype.sales_order.sales_order import update_status as update_sales_order_status

		work_orders = frappe.get_all("Work Order", filters={
			"print_order": self.name,
			"docstatus": 1,
			"status": ["=", "Stopped"]
		}, pluck="name")

		for name in work_orders:
			stop_unstop(name, "Resumed")

		sales_orders = frappe.db.sql_list("""
			select distinct so.name
			from `tabSales Order` so
			inner join `tabSales Order Item` i on i.parent = so.name
			where so.docstatus = 1 and i.print_order = %s and so.status = 'Closed'
		""", self.name)

		for name in sales_orders:
			update_sales_order_status("Re-Opened", name)

	def validate_order_defaults(self):
		validate_uom_and_qty_type(self)

	def validate_wastage(self):
		allowance = flt(frappe.db.get_single_value("Manufacturing Settings", "overproduction_percentage_for_work_order"))
		wastage_mandatory = cint(frappe.db.get_single_value("Fabric Printing Settings", "wastage_mandatory"))
		for d in self.items:
			if wastage_mandatory and flt(d.per_wastage) <= 0:
				frappe.throw(_("Row #{0}: Wastage cannot be zero").format(d.idx))

			if flt(d.per_wastage) > allowance:
				frappe.throw(_("Row #{0}: Wastage cannot be greater than Over Production Allowance of {1}").format(
					d.idx, frappe.bold(frappe.format(allowance, df=d.meta.get_field("per_wastage")))
				))

	def validate_process_items(self):
		if self.get("process_item"):
			validate_textile_item(self.process_item, "Print Process")

		for component_item_field, component_type in printing_components.items():
			if self.get(component_item_field):
				validate_textile_item(self.get(component_item_field), "Process Component", component_type)

		if self.docstatus == 1:
			if not self.get("process_item"):
				frappe.throw(_("Process Item is mandatory for submission"))

			for component_item_field in printing_components:
				if self.get(f"{component_item_field}_required"):
					field_label = self.meta.get_label(component_item_field)

					if not self.get(component_item_field):
						frappe.throw(_("{0} is mandatory for submission").format(frappe.bold(field_label)))

					component_item_name = self.get(f"{component_item_field}_name") or self.get(component_item_field)
					if self.get(f"{component_item_field}_by_fabric_weight"):
						if not self.fabric_gsm:
							frappe.throw(_("Fabric GSM is mandatory for {0} {1}. Please set Fabric GSM in {2}").format(
								field_label,
								frappe.bold(component_item_name),
								frappe.get_desk_link("Item", self.fabric_item)
							))
						if not self.fabric_per_pickup:
							frappe.throw(_("Fabric Pickup % is mandatory for {0} {1}. Please set Fabric Pickup % in {2}").format(
								field_label,
								frappe.bold(component_item_name),
								frappe.get_desk_link("Item", self.fabric_item)
							))

	def validate_design_items(self):
		if self.docstatus == 1 and not self.items:
			frappe.throw(_("Design Items cannot be empty."))

		for d in self.items:
			if d.design_image and not d.design_width or not d.design_height:
				frappe.throw(_("Row #{0}: Image Dimensions cannot be empty").format(d.idx))

			if flt(d.qty) <= 0:
				frappe.throw(_("Row #{0}: Qty must be greater than 0").format(d.idx))

			if d.design_width > self.fabric_width:
				frappe.msgprint(_("Row #{0}: Design Width {1} is greater than Fabric Width {2}").format(
					d.idx, d.design_width, self.fabric_width), indicator='orange')

	def calculate_totals(self):
		self.total_print_length = 0
		self.total_fabric_length = 0
		self.total_panel_qty = 0

		conversion_factors = get_textile_conversion_factors()

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

			d.print_length = flt(d.print_length, d.precision("print_length"))
			d.fabric_length = flt(d.fabric_length, d.precision("fabric_length"))

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
			"fabric_gsm": self.fabric_gsm,
			"fabric_width": self.fabric_width,
			"fabric_per_pickup": self.fabric_per_pickup,
		})

		process_conditions = ["p.process_item = %(process_item)s"]

		for component_item_field in printing_components:
			if self.get(f"{component_item_field}_required"):
				process_conditions.append(f"p.{component_item_field}_required = 1")
				process_conditions.append(f"p.{component_item_field} = %({component_item_field})s")

				if self.meta.has_field(f"{component_item_field}_by_fabric_weight"):
					process_conditions.append(f"{component_item_field}_by_fabric_weight = %({component_item_field}_by_fabric_weight)s")

					if self.get(f"{component_item_field}_by_fabric_weight"):
						process_conditions.append("p.fabric_gsm = %(fabric_gsm)s")
						process_conditions.append("p.fabric_per_pickup = %(fabric_per_pickup)s")
						process_conditions.append("p.fabric_width = %(fabric_width)s")
			else:
				process_conditions.append(f"p.{component_item_field}_required = 0")

			filters[component_item_field] = self.get(component_item_field)
			filters[f"{component_item_field}_by_fabric_weight"] = cint(self.get(f"{component_item_field}_by_fabric_weight"))

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

	def create_work_orders(self, publish_progress=True, ignore_version=True, ignore_feed=True):
		if self.docstatus != 1:
			frappe.throw(_("Print Order is not submitted"))

		if not all(d.item_code and d.design_bom for d in self.items):
			frappe.throw(_("Create Items and BOMs first"))

		if self.is_internal_customer:
			wo_list = self.create_work_orders_against_print_order(publish_progress=publish_progress,
				ignore_version=ignore_version, ignore_feed=ignore_feed)
		else:
			wo_list = self.create_work_order_against_sales_order(publish_progress=publish_progress,
				ignore_version=ignore_version, ignore_feed=ignore_feed)

		if wo_list:
			wo_message = _("Work Orders created: {0}").format(
				", ".join([frappe.utils.get_link_to_form('Work Order', wo) for wo in wo_list])
			)
			frappe.msgprint(wo_message, indicator='green')

	def create_work_orders_against_print_order(self, publish_progress=True, ignore_version=True, ignore_feed=True):
		from erpnext.manufacturing.doctype.work_order.work_order import create_work_orders

		wo_list = []

		for i, d in enumerate(self.items):
			pending_qty = flt(d.stock_print_length) - flt(d.work_order_qty)
			pending_qty = round_up(pending_qty, frappe.get_precision("Work Order", "qty"))

			if pending_qty <= 0:
				continue

			work_order_item = {
				"print_order": self.name,
				"print_order_item": d.name,
				"item_code": d.item_code,
				"item_name": d.item_name,
				"bom_no": d.design_bom,
				"warehouse": self.fg_warehouse,
				"production_qty": pending_qty,
				"customer": self.customer,
				"customer_name": self.customer_name,
				"cost_center": self.get("cost_center"),
			}

			wo_list += create_work_orders([work_order_item], self.company, ignore_version=ignore_version,
				ignore_feed=ignore_feed)

			if publish_progress:
				publish_print_order_progress(self.name, "Creating Work Orders", i + 1, len(self.items))

		if not wo_list:
			frappe.msgprint(_("Work Orders already created"))

		return wo_list

	def create_work_order_against_sales_order(self, publish_progress=True, ignore_version=True, ignore_feed=True):
		from erpnext.manufacturing.doctype.work_order.work_order import create_work_orders

		sales_orders = frappe.get_all("Sales Order Item", 'distinct parent as sales_order', {
			'print_order': self.name,
			'docstatus': 1
		}, pluck="sales_order")

		if not sales_orders:
			frappe.throw(_("Please create Sales Order first"))

		wo_items = []
		for so in sales_orders:
			so_doc = frappe.get_doc('Sales Order', so)
			wo_items += so_doc.get_work_order_items(item_condition=lambda d: d.print_order == self.name)

		wo_list = []
		for i, d in enumerate(wo_items):
			wo_list += create_work_orders([d], self.company, ignore_version=ignore_version, ignore_feed=ignore_feed)
			if publish_progress:
				publish_print_order_progress(self.name, "Creating Work Orders", i + 1, len(wo_items))

		if not wo_list:
			frappe.msgprint(_("Work Order already created"))

		return wo_list

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

		if self.skip_transfer or (self.status == "Closed" and rounded_transfer_qty <= 0):
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
				select sum(IF(i.t_warehouse = %(wip_warehouse)s, i.stock_qty, -1 * i.stock_qty))
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

		production_within_allowance = self.per_work_ordered >= 100 and self.per_produced > 0 and not data.has_work_order_to_produce
		self.production_status = self.get_completion_status('per_produced', 'Produce',
			not_applicable=self.status == "Closed" or not self.per_work_ordered,
			within_allowance=production_within_allowance)

		packing_within_allowance = self.per_work_ordered >= 100 and self.per_packed > 0 and not data.has_work_order_to_pack
		self.packing_status = self.get_completion_status('per_packed', 'Pack',
			not_applicable=self.is_internal_customer or self.status == "Closed" or not self.packing_slip_required or not self.per_produced,
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
		out.has_work_order_to_pack = False
		out.has_work_order_to_produce = False

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				# Work Order
				work_order_data = frappe.db.sql("""
					SELECT print_order_item, qty, completed_qty, production_status, subcontracting_status, packing_status
					FROM `tabWork Order`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in work_order_data:
					out.work_order_qty_map.setdefault(d.print_order_item, 0)
					out.work_order_qty_map[d.print_order_item] += flt(d.qty)

					out.produced_qty_map.setdefault(d.print_order_item, 0)
					out.produced_qty_map[d.print_order_item] += flt(d.completed_qty)

					if d.production_status == "To Produce" or d.subcontracting_status == "To Receive":
						out.has_work_order_to_produce = True
					if d.packing_status != "Packed":
						out.has_work_order_to_pack = True

				# Packing Slips
				out.packed_qty_map = dict(frappe.db.sql("""
					select print_order_item, sum(packed_qty * conversion_factor)
					from `tabSales Order Item`
					where docstatus = 1 and print_order_item in %s
					group by print_order_item
				""", [row_names]))

		return out

	def validate_work_order_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('work_order_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

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
			not_applicable=self.is_internal_customer or self.status == "Closed" or (not self.per_ordered and not self.per_work_ordered),
			within_allowance=within_allowance)

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
				out.delivered_qty_map = dict(frappe.db.sql("""
					select print_order_item, sum(delivered_qty * conversion_factor)
					from `tabSales Order Item`
					where docstatus = 1 and print_order_item in %s
					group by print_order_item
				""", [row_names]))

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

	def _background_start_print_order(self, fabric_transfer_qty, publish_progress=True):
		self._start_print_order.catch(self, fabric_transfer_qty=fabric_transfer_qty, publish_progress=publish_progress)

	@frappe.catch_realtime_msgprint()
	def _start_print_order(self, fabric_transfer_qty, publish_progress=True):
		frappe.flags.skip_print_order_status_update = True

		# Design Items
		if not all(d.item_code and d.design_bom for d in self.items):
			self._create_design_items_and_boms(publish_progress=publish_progress, ignore_version=True, ignore_feed=True)

		# Fabric Transfer
		if flt(fabric_transfer_qty) > 0 and not self.skip_transfer:
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
		if flt(self.per_ordered) < 100 and not self.is_internal_customer:
			if publish_progress:
				publish_print_order_progress(self.name, "Creating Sales Order", 0, 1)

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

			if publish_progress:
				publish_print_order_progress(self.name, "Creating Sales Order", 1, 1)

		# Work Orders
		if flt(self.per_work_ordered) < 100:
			self.create_work_orders(publish_progress=publish_progress, ignore_version=True, ignore_feed=True)

		# Status Update
		frappe.flags.skip_print_order_status_update = False

		self.set_item_creation_status(update=True)
		self.set_fabric_transfer_status(update=True)
		self.set_sales_order_status(update=True)
		self.set_production_packing_status(update=True)
		self.set_delivery_status(update=True)
		self.set_status(update=True)

		self.validate_ordered_qty()
		self.validate_work_order_qty()

		self.notify_update()

	def _create_design_items_and_boms(self, publish_progress=True, ignore_version=True, ignore_feed=True):
		for i, d in enumerate(self.items):
			if not d.item_code:
				item_doc = self.make_design_item(d)
				item_doc.flags.ignore_version = ignore_version
				item_doc.flags.ignore_feed = ignore_feed
				item_doc.flags.ignore_permissions = True
				item_doc.flags.from_print_order = True
				item_doc.save()

				d.db_set({
					"item_code": item_doc.name,
					"item_name": item_doc.item_name
				})

			if not d.design_bom:
				bom_doc = self.make_design_bom(d)
				bom_doc.flags.ignore_version = ignore_version
				bom_doc.flags.ignore_feed = ignore_feed
				bom_doc.flags.ignore_permissions = True
				bom_doc.save()
				bom_doc.submit()

				d.db_set("design_bom", bom_doc.name)

			if publish_progress:
				publish_print_order_progress(self.name, "Creating Design Items and BOMs", i + 1, len(self.items))

		if not frappe.flags.skip_print_order_status_update:
			self.set_item_creation_status(update=True)
			self.notify_update()

		frappe.msgprint(_("Design Items and BOMs created successfully."))

	def make_design_item(self, design_item_row):
		if not design_item_row:
			frappe.throw(_('Print Order Row is mandatory.'))
		if not self.fabric_item:
			frappe.throw(_('Fabric Item is mandatory.'))

		default_item_group = frappe.db.get_single_value("Fabric Printing Settings",
			"default_item_group_for_printed_design_item")

		if not default_item_group:
			frappe.throw(_("Select Default Item Group for Printed Design Item in Fabric Printing Settings."))

		item_doc = frappe.new_doc("Item")
		if item_doc.item_naming_by == "Item Code":
			item_doc.item_naming_by = "Naming Series"

		item_doc.update({
			"item_group": default_item_group,
			"textile_item_type": "Printed Design",
			"item_name": design_item_row.design_name,
			"stock_uom": design_item_row.stock_uom,
			"fabric_item": self.fabric_item,
			"image": design_item_row.design_image,
			"design_width": design_item_row.design_width,
			"design_height": design_item_row.design_height,
			"design_gap": design_item_row.design_gap,
			"per_wastage": design_item_row.per_wastage,
			"design_notes": design_item_row.design_notes,
			"customer": self.customer,
			"default_material_request_type": "Manufacture",
		})

		if item_doc.meta.has_field("cost_center") and self.get("cost_center"):
			item_doc.cost_center = self.get("cost_center")

		item_doc.append("uom_conversion_graph", {
			"from_uom": "Panel",
			"from_qty": 1,
			"to_uom": "Meter",
			"to_qty": design_item_row.panel_length_meter
		})

		return item_doc

	def make_design_bom(self, design_item_row):
		if not design_item_row.item_code:
			frappe.throw(_('Design Item is mandatory.'))
		if not self.fabric_item:
			frappe.throw(_('Fabric Item is mandatory.'))
		if not self.process_item:
			frappe.throw(_('Process Item is mandatory.'))

		bom_doc = frappe.new_doc("BOM")
		bom_doc.update({
			"item": design_item_row.item_code,
			"quantity": 1,
		})

		if bom_doc.meta.has_field("cost_center") and self.get("cost_center"):
			bom_doc.cost_center = self.get("cost_center")

		self.validate_item_convertible_to_uom(self.fabric_item, "Meter")
		bom_doc.append("items", {
			"item_code": self.fabric_item,
			"qty": 1,
			"uom": "Meter",
			"skip_transfer_for_manufacture": 0,
			"do_not_explode": 1,
		})

		self.validate_item_has_bom(self.process_item)
		self.validate_item_convertible_to_uom(self.process_item, "Meter")
		bom_doc.append("items", {
			"item_code": self.process_item,
			"qty": 1,
			"uom": "Meter",
			"skip_transfer_for_manufacture": 1,
		})

		components = []
		for component_item_field in printing_components:
			if self.get(f"{component_item_field}_required"):
				component = frappe._dict({
					"item_code": self.get(component_item_field),
					"consumption_by_fabric_weight": cint(self.get(f"{component_item_field}_by_fabric_weight"))
				})

				components.append(component)

		self.add_components_to_bom(bom_doc, components, self.fabric_gsm, self.fabric_width, self.fabric_per_pickup)

		return bom_doc


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


def validate_transaction_against_print_order(doc):
	def get_order_details(name):
		if not order_map.get(name):
			order_map[name] = frappe.db.get_value("Print Order", name, [
				"name", "docstatus", "status", "company", "customer", "customer_name",
				"fg_warehouse", "is_internal_customer"
			], as_dict=1)

		return order_map[name]

	def get_line_details(name):
		if not line_map.get(name):
			line_map[name] = frappe.db.get_value("Print Order Item", name, ["item_code", "length_uom"], as_dict=1)

		return line_map[name]

	order_map = {}
	line_map = {}
	visited_lines = set()

	for d in doc.get("items"):
		if not d.get("print_order"):
			continue

		if d.get("print_order_item"):
			if doc.doctype == "Sales Order" and d.print_order_item in visited_lines:
				frappe.throw(_("Duplicate row {0} with same {1}").format(d.idx, _("Print Order")))
			else:
				visited_lines.add(d.print_order_item)

		order_details = get_order_details(d.print_order)
		if not order_details:
			frappe.throw(_("Row #{0}: Print Order {1} does not exist").format(d.idx, d.print_order))

		if order_details.docstatus == 0:
			frappe.throw(_("Row #{0}: {1} is in draft").format(
				d.idx, frappe.get_desk_link("Print Order", order_details.name)
			))
		if order_details.docstatus == 2:
			frappe.throw(_("Row #{0}: {1} is cancelled").format(
				d.idx, frappe.get_desk_link("Print Order", order_details.name)
			))

		if order_details.status == "Closed" and not doc.get("is_return") and doc.doctype != "Sales Invoice":
			frappe.throw(_("Row #{0}: {1} is {2}").format(
				d.idx,
				frappe.get_desk_link("Print Order", order_details.name),
				frappe.bold(order_details.status)
			))

		if order_details.is_internal_customer:
			frappe.throw(_("Row #{0}: Cannot create {1} against {2} because it is against an internal customer {3}").format(
				d.idx,
				doc.doctype,
				frappe.get_desk_link("Print Order", order_details.name),
				frappe.bold(order_details.customer_name or order_details.customer)
			))

		if doc.company != order_details.company:
			frappe.throw(_("Row #{0}: Company does not match with {1}. Company must be {2}").format(
				d.idx,
				frappe.get_desk_link("Print Order", order_details.name),
				order_details.company
			))

		if doc.customer != order_details.customer:
			frappe.throw(_("Row #{0}: Customer does not match with {1}. Customer must be {2}").format(
				d.idx,
				frappe.get_desk_link("Print Order", order_details.name),
				order_details.customer_name or order_details.customer
			))

		if doc.doctype == "Sales Order" and d.warehouse != order_details.fg_warehouse:
			frappe.throw(_("Row #{0}: Warehouse does not match with {1}. Warehouse must be {2}").format(
				d.idx,
				frappe.get_desk_link("Print Order", order_details.name),
				order_details.warehouse
			))

		if d.get("print_order_item"):
			line_details = get_line_details(d.print_order_item)

			if d.item_code != line_details.item_code:
				frappe.throw(_("Row #{0}: Item Code does not match with {1}. Item Code must be {2}").format(
					d.idx,
					frappe.get_desk_link("Print Order", order_details.name),
					line_details.item_code
				))

			if d.uom != line_details.length_uom:
				frappe.throw(_("Row #{0}: UOM does not match with {1}. UOM must be {2}").format(
					d.idx,
					frappe.get_desk_link("Print Order", order_details.name),
					line_details.length_uom
				))


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

	if status == "Closed":
		doc.close_linked_documents()
	elif status != "Closed" and doc.status == "Closed":
		doc.reopen_linked_documents()

	doc.run_method("update_status", status)


@frappe.whitelist()
def close_or_unclose_print_orders(names, status):
	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		update_status(name, status)


@frappe.whitelist()
def start_print_order(print_order, fabric_transfer_qty=None):
	from erpnext.stock.stock_ledger import get_allow_negative_stock

	doc = frappe.get_doc('Print Order', print_order)

	if doc.docstatus != 1:
		frappe.throw(_("Print Order {0} is not submitted").format(doc.name))
	if doc.status == "Closed":
		frappe.throw(_("Print Order {0} is Closed").format(doc.name))

	if doc.skip_transfer:
		fabric_transfer_qty = None
	else:
		fabric_transfer_qty = flt(fabric_transfer_qty, precision=doc.precision("total_fabric_length"))
		if fabric_transfer_qty > 0 and fabric_transfer_qty > doc.fabric_stock_qty and not get_allow_negative_stock():
			frappe.throw(_("Not enough Ready Fabric Item {0} in Fabric Warehouse ({1} Meter in stock)").format(
				frappe.utils.get_link_to_form("Item", doc.fabric_item), doc.get_formatted("fabric_stock_qty")
			))

	if len(doc.items) > 5:
		doc.queue_action("_background_start_print_order", fabric_transfer_qty=fabric_transfer_qty, timeout=1800)
		frappe.msgprint(_("Starting Print Order in background..."), alert=True)
	else:
		doc._start_print_order(fabric_transfer_qty=fabric_transfer_qty)


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
		doc.queue_action("_create_design_items_and_boms", timeout=600)
		frappe.msgprint(_("Creating Design Items and BOMs..."), alert=True)
	else:
		doc._create_design_items_and_boms()


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	return _make_sales_order(source_name, target_doc)


def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	def set_missing_values(source, target):
		if target.meta.has_field("cost_center") and source.get("cost_center"):
			target.cost_center = source.get("cost_center")

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
	}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

	return doc


@frappe.whitelist()
def create_work_orders(print_order, publish_progress=True, ignore_version=True, ignore_feed=True):
	doc = frappe.get_doc("Print Order", print_order)
	doc.create_work_orders(publish_progress=publish_progress, ignore_version=ignore_version, ignore_feed=ignore_feed)


@frappe.whitelist()
def make_fabric_transfer_entry(print_order, fabric_transfer_qty=None, for_submit=False):
	if isinstance(print_order, str):
		doc = frappe.get_doc('Print Order', print_order)
	else:
		doc = print_order

	if not all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Create Items and BOMs first"))

	if doc.skip_transfer:
		frappe.throw(_("Fabric Transfer not required against Print Order {0}").format(doc.name))

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.purpose = "Material Transfer for Manufacture"
	stock_entry.print_order = doc.name
	stock_entry.company = doc.company
	stock_entry.from_warehouse = doc.fabric_warehouse
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

	if stock_entry.meta.has_field("cost_center") and doc.get("cost_center"):
		stock_entry.cost_center = doc.get("cost_center")

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
	else:
		selected_children = frappe.get_all("Sales Order Item", filters={"print_order": doc.name}, pluck="name")
		frappe.flags.selected_children = {"items": selected_children}

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.per_packed < 100 AND i.skip_delivery_note = 0
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

	selected_children = frappe.get_all("Sales Order Item", filters={"print_order": doc.name}, pluck="name")
	frappe.flags.selected_children = {"items": selected_children}

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
			AND s.per_delivered < 100 AND i.skip_delivery_note = 0
			AND s.company = %(company)s AND i.print_order = %(print_order)s
	""", {"print_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be delivered"))

	packing_filter = "Packed Items Only" if doc.packing_slip_required else None

	for d in sales_orders:
		target_doc = make_delivery_note_from_packing_slips(d.name, target_doc=target_doc, packing_filter=packing_filter)

	if doc.packing_slip_required and not target_doc:
		frappe.throw(_("There are no packed Sales Orders to be delivered"))

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
def get_image_details(image_url, throw_not_found=True):
	doc_name = frappe.get_value('File', filters={'file_url': image_url})

	if not doc_name:
		frappe.throw(_("File {0} not found").format(image_url))

	file_doc = frappe.get_doc("File", doc_name)
	file_name = file_doc.get("original_file_name") or file_doc.file_name

	out = frappe._dict()
	out.design_name = ".".join(file_name.split('.')[:-1]) or file_name

	file_full_path = file_doc.get_full_path()
	try:
		im = Image.open(file_full_path)
		out.design_width = flt(im.size[0] / 10, 1)
		out.design_height = flt(im.size[1] / 10, 1)
	except FileNotFoundError:
		frappe.msgprint(_("Design {0} file not found").format(out.design_name or file_full_path),
			raise_exception=throw_not_found, indicator="red" if throw_not_found else "orange")

	return out


@frappe.whitelist()
def get_fabric_item_details(fabric_item, get_default_process=True):
	from textile.utils import get_fabric_item_details

	out = get_fabric_item_details(fabric_item)

	if fabric_item and cint(get_default_process):
		process_details = get_default_print_process(fabric_item)
		out.update(process_details)

	return out


@frappe.whitelist()
def get_default_print_process(fabric_item):
	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()
	out = frappe._dict()

	# Set process values as None to unset in UI
	out.process_item = None
	out.process_item_name = None

	for component_item_field in printing_components:
		out[component_item_field] = None
		out[f"{component_item_field}_name"] = None
		out[f"{component_item_field}_required"] = 0
		out[f"{component_item_field}_separate_process"] = 0

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

	for component_item_field in printing_components:
		out[f"{component_item_field}_required"] = process_doc.get(f"{component_item_field}_required")
		out[f"{component_item_field}_separate_process"] = process_doc.get(f"{component_item_field}_separate_process")

	if fabric_item and process_item and cint(get_default_paper):
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


@frappe.whitelist()
def get_process_component_details(component_item_code, component_item_field):
	component_item_doc = frappe.get_cached_doc("Item", component_item_code) if component_item_code else frappe._dict()

	out = frappe._dict()
	out[f"{component_item_field}_name"] = component_item_doc.item_name
	out[f"{component_item_field}_by_fabric_weight"] = component_item_doc.consumption_by_fabric_weight

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
