# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.mapper import get_mapped_doc
from erpnext.accounts.party import validate_party_frozen_disabled
from erpnext.controllers.status_updater import StatusUpdater
from PIL import Image
import json


default_fields_map = {
	"default_printing_uom": "default_uom",
	"default_printing_gap": "default_gap",
	"default_printing_qty_type": "default_qty_type",
	"default_printing_length_uom": "default_length_uom"
}


class PrintOrder(StatusUpdater):
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
		self.validate_customer()
		self.validate_fabric_item()
		self.validate_process_item()
		self.validate_design_items()
		self.validate_order_defaults()
		self.calculate_totals()

		if self.docstatus == 1:
			self.set_existing_items_and_boms()

		self.set_status()
		self.set_title()

	def on_submit(self):
		self.set_order_defaults_for_customer()

	def set_missing_values(self):
		self.attach_unlinked_item_images()
		self.set_design_details_from_image()

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

		if self.docstatus == 0:
			self.status = "Draft"

		elif self.docstatus == 1:
			if not all(d.item_code and d.design_bom for d in self.items):
				self.status = "To Create Items"
			elif self.per_ordered < 100:
				self.status = "To Confirm Order"
			elif self.per_work_ordered < 100:
				self.status = "To Order Production"
			elif self.per_produced < 100:
				self.status = "To Finish Production"
			elif self.per_delivered < 100:
				self.status = "To Deliver"
			elif self.per_billed < 100:
				self.status = "To Bill"
			else:
				self.status = "Completed"

		else:
			self.status = "Cancelled"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)

	def set_title(self):
		self.title = self.customer_name or self.customer

	def validate_order_defaults(self):
		validate_uom_and_qty_type(self)

	def validate_customer(self):
		if self.get("customer"):
			validate_party_frozen_disabled("Customer", self.customer)

	def validate_fabric_item(self):
		if self.get("fabric_item"):
			validate_print_item(self.fabric_item, "Fabric")

			item_details = frappe.get_cached_value("Item", self.fabric_item, ["is_customer_provided_item", "customer"], as_dict=1)

			if self.is_fabric_provided_by_customer != item_details.is_customer_provided_item:
				if not item_details.is_customer_provided_item:
					frappe.throw(_("Fabric Item {0} is not a Customer Provided Item").format(frappe.bold(self.fabric_item)))
				else:
					frappe.throw(_("Fabric Item {0} is a Customer Provided Item").format(frappe.bold(self.fabric_item)))

			if self.is_fabric_provided_by_customer and self.customer and self.customer != item_details.customer:
				frappe.throw(_("Customer Provided Fabric Item {0} does not belong to Customer {1}").format(
					frappe.bold(self.fabric_item), frappe.bold(self.customer)))

	def validate_process_item(self):
		if self.get("process_item"):
			validate_print_item(self.process_item, "Print Process")

	def validate_design_items(self):
		if self.docstatus == 1 and not self.items:
			frappe.throw(_("Design Items cannot be empty."))

		for d in self.items:
			if d.design_image and not (d.design_width or d.design_height):
				frappe.throw(_("Row #{0}: Image Dimensions cannot be empty").format(d.idx))

			if not d.qty:
				frappe.throw(_("Row #{0}: Qty cannot be 0").format(d.idx))

	def attach_unlinked_item_images(self):
		filters = {
			'attached_to_doctype': self.doctype,
			'attached_to_name': self.name
		}
		files = frappe.db.get_all('File', filters, ['file_url'])

		attached_images = {d.file_url for d in files}
		linked_images = {d.design_image for d in self.items}
		unlinked_images = attached_images - linked_images

		if not unlinked_images:
			return

		for file_url in unlinked_images:
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

			design_details = self.get_image_details(d.design_image)
			d.update(design_details)

	@frappe.whitelist()
	def get_image_details(self, image_url):
		doc_name = frappe.get_value('File', filters={'file_url': image_url})

		if not doc_name:
			frappe.throw(_("File {0} not found").format(image_url))

		file_doc = frappe.get_doc("File", doc_name)

		out = frappe._dict()
		out.design_name = ".".join(file_doc.file_name.split('.')[:-1]) or file_doc.file_name

		im = Image.open(file_doc.get_full_path())
		out.design_width = flt(im.size[0] / 10, 1)
		out.design_height = flt(im.size[1] / 10, 1)

		return out

	def calculate_totals(self):
		self.total_print_length = 0
		self.total_fabric_length = 0
		self.total_panel_qty = 0

		conversion_factors = {
			'inch_to_meter': 0.0254,
			'yard_to_meter': 0.9144, 
			'meter_to_meter': 1
		}

		for d in self.items:
			validate_uom_and_qty_type(d)
			self.round_floats_in(d)

			d.panel_length_inch = flt(d.design_height) + flt(d.design_gap)
			d.panel_length_meter = d.panel_length_inch * conversion_factors['inch_to_meter']
			d.panel_length_yard = d.panel_length_meter / conversion_factors['yard_to_meter']

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
		filters = frappe._dict({
			'customer': self.customer,
			'fabric_item': self.fabric_item,
			'process_item': self.process_item,
		})

		for d in self.items:
			if d.item_code:
				continue

			filters.update({
				"design_image": d.design_image,
				"design_width": d.design_width,
				"design_height": d.design_height,
			})

			res = frappe.db.sql("""
				SELECT i.item_code
				FROM `tabPrint Order Item` i
				INNER JOIN `tabPrint Order` p ON p.name = i.parent
				WHERE p.docstatus = 1 AND p.customer = %(customer)s AND p.fabric_item = %(fabric_item)s
				AND p.process_item = %(process_item)s AND i.design_image = %(design_image)s
				AND i.design_width = %(design_width)s AND i.design_height = %(design_height)s
				AND ifnull(i.item_code, '') != ''
				ORDER BY p.creation DESC
			""", filters, as_dict=1)

			if not res:
				continue

			d.item_code = res[0].item_code or None
			if d.item_code:
				d.item_name = frappe.get_cached_value("Item", d.item_code, "item_name") if d.item_code else None
				d.design_bom = frappe.db.get_value("BOM", filters={
					"item": d.item_code, "is_default": 1, "docstatus": 1
				})

	def set_ordered_status(self, update=False, update_modified=True):
		data = self.get_ordered_status_data()

		for d in self.items:
			d.ordered_qty = flt(data.ordered_qty_map.get(d.name))
			if update:
				d.db_set({
					'ordered_qty': d.ordered_qty
				}, update_modified=update_modified)

		self.per_ordered = flt(self.calculate_status_percentage('ordered_qty', 'qty', self.items))
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
					SELECT i.print_order_item, i.qty
					FROM `tabSales Order Item` i
					INNER JOIN `tabSales Order` s ON s.name = i.parent
					WHERE s.docstatus = 1 AND i.print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in ordered_data:
					out.ordered_qty_map.setdefault(d.print_order_item, 0)
					out.ordered_qty_map[d.print_order_item] += flt(d.qty)

		return out

	def validate_ordered_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('ordered_qty', 'qty', self.items,
			from_doctype=from_doctype, row_names=row_names)

	def set_work_order_status(self, update=False, update_modified=True):
		data = self.get_work_order_status_data()

		for d in self.items:
			d.work_order_qty = flt(data.work_order_qty_map.get(d.name))
			if update:
				d.db_set({
					'work_order_qty': d.work_order_qty
				}, update_modified=update_modified)

		self.per_work_ordered = flt(self.calculate_status_percentage('work_order_qty', 'stock_print_length', self.items))
		if update:
			self.db_set({
				'per_work_ordered': self.per_work_ordered
			}, update_modified=update_modified)

	def get_work_order_status_data(self):
		out = frappe._dict()
		out.work_order_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				work_order_data = frappe.db.sql("""
					SELECT print_order_item, qty
					FROM `tabWork Order`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in work_order_data:
					out.work_order_qty_map.setdefault(d.print_order_item, 0)
					out.work_order_qty_map[d.print_order_item] += flt(d.qty)

		return out

	def validate_work_order_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('work_order_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

	def set_produced_status(self, update=False, update_modified=True):
		data = self.get_produced_status_data()

		for d in self.items:
			d.produced_qty = flt(data.produced_qty_map.get(d.name))
			if update:
				d.db_set({
					'produced_qty': d.produced_qty
				}, update_modified=update_modified)

		self.per_produced = flt(self.calculate_status_percentage('produced_qty', 'stock_print_length', self.items))
		if update:
			self.db_set({
				'per_produced': self.per_produced
			}, update_modified=update_modified)

	def get_produced_status_data(self):
		out = frappe._dict()
		out.produced_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				produced_data = frappe.db.sql("""
					SELECT print_order_item, produced_qty
					FROM `tabWork Order`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in produced_data:
					out.produced_qty_map.setdefault(d.print_order_item, 0)
					out.produced_qty_map[d.print_order_item] += flt(d.produced_qty)

		return out

	def validate_produced_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('produced_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

	def set_packed_status(self, update=False, update_modified=True):
		data = self.get_packed_status_data()

		for d in self.items:
			d.packed_qty = flt(data.packed_qty_map.get(d.name))
			if update:
				d.db_set({
					'packed_qty': d.packed_qty
				}, update_modified=update_modified)

		self.per_packed = flt(self.calculate_status_percentage('packed_qty', 'stock_print_length', self.items))
		if update:
			self.db_set({
				'per_packed': self.per_packed
			}, update_modified=update_modified)

	def get_packed_status_data(self):
		out = frappe._dict()
		out.packed_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				packed_data = frappe.db.sql("""
					SELECT print_order_item, qty
					FROM `tabPacking Slip Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in packed_data:
					out.packed_qty_map.setdefault(d.print_order_item, 0)
					out.packed_qty_map[d.print_order_item] += flt(d.qty)

		return out

	def validate_packed_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('packed_qty', 'stock_print_length', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="production")

	def set_delivered_status(self, update=False, update_modified=True):
		data = self.get_delivered_status_data()

		for d in self.items:
			d.delivered_qty = flt(data.delivered_qty_map.get(d.name))
			if update:
				d.db_set({
					'delivered_qty': d.delivered_qty
				}, update_modified=update_modified)

		self.per_delivered = flt(self.calculate_status_percentage('delivered_qty', 'qty', self.items))
		if update:
			self.db_set({
				'per_delivered': self.per_delivered
			}, update_modified=update_modified)

	def get_delivered_status_data(self):
		out = frappe._dict()
		out.delivered_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				delivered_data = frappe.db.sql("""
					SELECT print_order_item, qty
					FROM `tabDelivery Note Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in delivered_data:
					out.delivered_qty_map.setdefault(d.print_order_item, 0)
					out.delivered_qty_map[d.print_order_item] += flt(d.qty)

		return out

	def validate_delivered_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('delivered_qty', 'qty', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="qty")

	def set_billed_status(self, update=False, update_modified=True):
		data = self.get_billed_status_data()

		for d in self.items:
			d.billed_qty = flt(data.billed_qty_map.get(d.name))
			if update:
				d.db_set({
					'billed_qty': d.billed_qty
				}, update_modified=update_modified)

		self.per_billed = flt(self.calculate_status_percentage('billed_qty', 'qty', self.items))
		if update:
			self.db_set({
				'per_billed': self.per_billed
			}, update_modified=update_modified)

	def get_billed_status_data(self):
		out = frappe._dict()
		out.billed_qty_map = {}

		if self.docstatus == 1:
			row_names = [d.name for d in self.items]
			if row_names:
				billed_data = frappe.db.sql("""
					SELECT print_order_item, qty
					FROM `tabSales Invoice Item`
					WHERE docstatus = 1 AND print_order_item IN %s
				""", [row_names], as_dict=1)

				for d in billed_data:
					out.billed_qty_map.setdefault(d.print_order_item, 0)
					out.billed_qty_map[d.print_order_item] += flt(d.qty)

		return out

	def validate_billed_qty(self, from_doctype=None, row_names=None):
		self.validate_completed_qty('billed_qty', 'qty', self.items,
			from_doctype=from_doctype, row_names=row_names, allowance_type="billing")


def validate_print_item(item_code, print_item_type):
	item = frappe.get_cached_doc("Item", item_code)

	if print_item_type:
		if item.print_item_type != print_item_type:
			frappe.throw(_("{0} is not a {1} Item").format(frappe.bold(item_code), print_item_type))

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
def create_design_items_and_boms(print_order):
	doc = frappe.get_doc('Print Order', print_order)

	if doc.docstatus != 1:
		frappe.throw(_("Submit the Print Order first."))

	if all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Printed Design Items and BOMs already created."))

	for d in doc.items:
		if not d.item_code:
			item_doc = make_design_item(d, doc.fabric_item, doc.process_item)
			item_doc.save()

			d.db_set({
				"item_code": item_doc.name,
				"item_name": item_doc.item_name
			})

		if not d.design_bom:
			bom_doc = make_design_bom(d.item_code, doc.fabric_item, doc.process_item)

			bom_doc.save()
			bom_doc.submit()

			d.db_set("design_bom", bom_doc.name)

	doc.set_status(update=True)
	frappe.msgprint(_("Design Items and BOMs created successfully."))


def make_design_item(design_item_row, fabric_item, process_item):
	if not design_item_row:
		frappe.throw(_('Print Order Row is mandatory.'))
	if not fabric_item:
		frappe.throw(_('Fabric Item is mandatory.'))
	if not process_item:
		frappe.throw(_('Process Item is mandatory.'))

	default_item_group = frappe.db.get_single_value("Digital Printing Settings", "default_item_group_for_printed_design_item")
	fabric_item_name = frappe.get_cached_value('Item', fabric_item, 'item_name')

	if not default_item_group:
		frappe.throw(_("Select Default Item Group for Printed Design Item in Digital Printing Settings."))

	item_doc = frappe.new_doc("Item")
	if item_doc.item_naming_by == "Item Code":
		item_doc.item_naming_by  = "Naming Series"

	item_doc.update({
		"item_group": default_item_group,
		"print_item_type": "Printed Design",
		"item_name": "{0} ({1})".format(design_item_row.design_name, fabric_item_name),
		"stock_uom": design_item_row.stock_uom,
		"sales_uom": design_item_row.uom,
		"fabric_item": fabric_item,
		"process_item": process_item,
		"image": design_item_row.design_image,
		"design_name": design_item_row.design_name,
		"design_width": design_item_row.design_width,
		"design_height": design_item_row.design_height,
		"design_gap": design_item_row.design_gap,
		"per_wastage": design_item_row.per_wastage,
		"design_notes": design_item_row.design_notes,
	})

	item_doc.append("uom_conversion_graph", {
		"from_uom": "Panel",
		"from_qty": 1,
		"to_uom": "Meter",
		"to_qty": design_item_row.panel_length_meter
	})

	if "Yard" in [design_item_row.length_uom, design_item_row.uom]:
		item_doc.append("uom_conversion_graph", {
			"from_uom": "Yard",
			"from_qty": 1,
			"to_uom": "Meter",
			"to_qty": 0.9144
		})

	return item_doc


def make_design_bom(design_item, fabric_item, process_item):
	if not design_item:
		frappe.throw(_('Design Item is mandatory.'))
	if not fabric_item:
		frappe.throw(_('Fabric Item is mandatory.'))
	if not process_item:
		frappe.throw(_('Process Item is mandatory.'))

	bom_doc = frappe.get_doc({
		"doctype": "BOM",
		"item": design_item,
		"quantity": 1
	})

	bom_doc.append("items", {
		"item_code": fabric_item,
		"qty": 1
	})
	bom_doc.append("items", {
		"item_code": process_item,
		"qty": 1
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

		return abs(source.ordered_qty) < abs(source.qty)

	def update_item(source, target, source_parent, target_parent):
		target.qty = flt(source.qty) - flt(source.ordered_qty)

	doc = get_mapped_doc("Print Order", source_name,	{
		"Print Order": {
			"doctype": "Sales Order",
			"field_map": {
				"delivery_date": "delivery_date",
				"set_warehouse": "set_warehouse",
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
				"item_code": "item_code"
			},
			"postprocess": update_item,
			"condition": item_condition,
		}
	}, target_doc, set_missing_values)

	return doc


@frappe.whitelist()
def create_work_orders(print_order):
	from erpnext.selling.doctype.sales_order.sales_order import make_work_orders
	doc = frappe.get_doc('Print Order', print_order)

	if doc.docstatus != 1:
		frappe.throw(_("Submit the Print Order first."))

	if not all(d.item_code and d.design_bom for d in doc.items):
		frappe.throw(_("Create Items and BOMs first"))

	if all(d.qty and d.ordered_qty < d.qty for d in doc.items):
		frappe.throw(_("Create Sales Order first"))

	if doc.per_work_ordered >= 100:
		frappe.throw(_("Work Orders already created."))

	sales_orders = frappe.get_all("Sales Order Item", 'parent', {'print_order': doc.name})
	sales_orders = {d.parent for d in sales_orders}

	wo_list = []
	for so in sales_orders:
		so_doc = frappe.get_doc('Sales Order', so)
		wo_items = so_doc.get_work_order_items()
		wo = make_work_orders(wo_items, so, so_doc.company)
		wo_list += wo

	if wo_list:
		frappe.msgprint(_("Work Orders Created: {0}").format(
			', '.join([frappe.utils.get_link_to_form('Work Order', wo) for wo in wo_list])
		), indicator='green')
	else:
		frappe.msgprint(_("Work Order already created in Draft."))


@frappe.whitelist()
def make_packing_slip(print_order):
	from erpnext.selling.doctype.sales_order.sales_order import make_packing_slip

	doc = frappe.get_doc("Print Order", print_order)

	target_doc = frappe.new_doc("Packing Slip")

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
		AND s.per_packed < 99.99 AND s.company = %(company)s AND
		i.print_order = %(print_order)s
	""", {"print_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be packed"))

	for d in sales_orders:
		target_doc = make_packing_slip(d.name, target_doc=target_doc)

	# Missing Values and Forced Values
	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_totals")

	return target_doc


@frappe.whitelist()
def make_delivery_note(print_order):
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note_from_packing_slips

	doc = frappe.get_doc("Print Order", print_order)

	target_doc = frappe.new_doc("Delivery Note")

	sales_orders = frappe.db.sql("""
		SELECT DISTINCT s.name
		FROM `tabSales Order Item` i
		INNER JOIN `tabSales Order` s ON s.name = i.parent
		WHERE s.docstatus = 1 AND s.status NOT IN ('Closed', 'On Hold')
		AND s.per_delivered < 99.99 AND s.skip_delivery_note = 0
		AND s.company = %(company)s AND i.print_order = %(print_order)s
	""", {"print_order": doc.name, "company": doc.company},  as_dict=1)

	if not sales_orders:
		frappe.throw(_("There are no Sales Orders to be delivered"))

	packing_filter = "Packed Items Only" if doc.packing_slip_required else None

	for d in sales_orders:
		target_doc = make_delivery_note_from_packing_slips(d.name, target_doc=target_doc, packing_filter=packing_filter)

	# Missing Values and Forced Values
	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_taxes_and_totals")

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

	# Missing Values and Forced Values
	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_taxes_and_totals")

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
		"t_warehouse": po_doc.fabric_warehouse,
		"uom": "Meter",
	})

	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_rate_and_amount")

	return target_doc
