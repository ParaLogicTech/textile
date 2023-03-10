# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from erpnext.accounts.party import validate_party_frozen_disabled
from PIL import Image


class PrintOrder(Document):
	def onload(self):
		self.set_missing_values()

	def validate(self):
		self.set_missing_values()
		self.validate_customer()
		self.validate_fabric_item()
		self.validate_process_item()
		self.validate_design_items()

	def set_missing_values(self):
		self.attach_unlinked_item_images()
		self.set_design_details_from_image()
		self.calculate_totals()

	def set_status(self, status=None, update=False, update_modified=True):
		previous_status = self.status

		if self.docstatus == 0:
			self.status = "Draft"

		elif self.docstatus == 1:
			if not all(d.item_code and d.design_bom for d in self.items):
				self.status = "To Create Items"

		else:
			self.status = "Cancelled"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)

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
			if d.design_width and d.design_height:
				continue
			if not d.design_image:
				continue

			design_details = self.get_image_details(d.design_image)
			d.update(design_details)

	@frappe.whitelist()
	def get_image_details(self, image_url):
		doc_name = frappe.get_value('File', filters={'file_url': image_url})

		if not doc_name:
			frappe.throw(_("File not found error"))

		out = frappe._dict()
		file_doc = frappe.get_doc("File", doc_name)

		out.design_name = file_doc.file_name.split('.')[0]
		im = Image.open(file_doc.get_full_path())
		out.design_width, out.design_height = im.size[0] / 10, im.size[1] / 10
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

	@frappe.whitelist()
	def on_upload_complete(self):
		self.set_missing_values()


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

	if "Yard" in [design_item_row.stock_uom, design_item_row.uom]:
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


def validate_print_item(item_code, print_item_type):
	item = frappe.get_cached_doc("Item", item_code)

	if print_item_type:
		if item.print_item_type != print_item_type:
			frappe.throw(_("{0} is not a {1} Item").format(frappe.bold(item_code), print_item_type))

	from erpnext.stock.doctype.item.item import validate_end_of_life
	validate_end_of_life(item.name, item.end_of_life, item.disabled)
