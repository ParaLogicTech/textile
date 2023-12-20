# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
from erpnext.stock.get_item_details import is_item_uom_convertible
from frappe.utils.status_updater import OverAllowanceError
from textile.controllers.textile_order import TextileOrder
from textile.utils import get_textile_conversion_factors, validate_textile_item
import copy


force_fields = ["customer_name", "fabric_item_name", "fabric_material",
	"fabric_type", "fabric_width", "fabric_gsm", "fabric_per_pickup"]


class CoatingOrder(TextileOrder):
	@property
	def fabric_stock_qty(self):
		return self.get_fabric_stock_qty(self.fabric_item, self.fabric_warehouse)

	def onload(self):
		if self.docstatus == 0:
			self.set_missing_values()
			self.calculate_totals()

	def validate(self):
		self.set_missing_values()
		self.validate_dates()
		self.validate_customer()
		self.validate_fabric_item("Ready Fabric")
		self.validate_coating_item()
		self.validate_qty()
		self.set_default_coating_bom()
		self.clean_remarks()
		self.calculate_totals()
		self.set_coating_status()
		self.set_status()

		self.set_title(self.fabric_material, self.stock_qty)

	def on_submit(self):
		self.validate_fabric_attributes()
		self.validate_uom_convertibility()

	def before_update_after_submit(self):
		self.validate_dates()

	def set_missing_values(self):
		self.set_fabric_item_details()

	def validate_coating_item(self):
		validate_textile_item(self.coating_item, "Process Component", "Coating")

	def validate_qty(self):
		if flt(self.qty) <= 0:
			frappe.throw(_("Qty must be greater than 0"))

	def validate_fabric_attributes(self):
		if self.coating_item_by_fabric_weight:
			if not self.fabric_width:
				frappe.throw(_("Fabric Width is mandatory for Coating Item {1}. Please set Fabric Pickup % in {2}").format(
					frappe.bold(self.coating_item_name),
					frappe.get_desk_link("Item", self.fabric_item)
				))
			if not self.fabric_gsm:
				frappe.throw(_("Fabric GSM is mandatory for Coating Item {1}. Please set Fabric Pickup % in {2}").format(
					frappe.bold(self.coating_item_name),
					frappe.get_desk_link("Item", self.fabric_item)
				))
			if not self.fabric_per_pickup:
				frappe.throw(_("Fabric Pickup % is mandatory for Coating Item {1}. Please set Fabric Pickup % in {2}").format(
					frappe.bold(self.coating_item_name),
					frappe.get_desk_link("Item", self.fabric_item)
				))

	def validate_uom_convertibility(self):
		conversion_uom = "Gram" if self.coating_item_by_fabric_weight else self.stock_uom

		if not is_item_uom_convertible(self.coating_item, conversion_uom):
			frappe.throw(_("{0} is not convertible to UOM {1}").format(
				frappe.get_desk_link("Item", self.fabric_item), frappe.bold(conversion_uom)
			))

	def calculate_totals(self):
		self.round_floats_in(self)
		conversion_factor = self.get_conversion_factor()
		self.stock_qty = self.qty * conversion_factor

	def set_default_coating_bom(self):
		self.coating_bom = get_default_coating_bom(self.coating_item, throw=self.docstatus == 1)

	def set_fabric_item_details(self):
		details = get_fabric_item_details(self.fabric_item, get_coating_item=False)
		for k, v in details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in force_fields):
				self.set(k, v)

	def set_status(self, status=None, update=False, update_modified=True):
		previous_status = self.status

		if status:
			self.status = status

		if self.docstatus == 0:
			self.status = 'Draft'

		elif self.docstatus == 1:
			if self.status == "Stopped":
				self.status = "Stopped"
			elif self.coating_status ==  "Coated":
				self.status = "Completed"
			elif self.has_stock_entry():
				self.status = "In Process"
			else:
				self.status = "Not Started"

		elif self.docstatus == 2:
			self.status = "Cancelled"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)

	def set_coating_status(self, update=False, update_modified=True):
		production_data = None
		if self.docstatus == 1:
			production_data = frappe.db.sql("""
				select sum(fg_completed_qty) as coated_qty, max(posting_date) as actual_end_date
				from `tabStock Entry`
				where docstatus = 1 and purpose = 'Manufacture' and coating_order = %s
			""", self.name, as_dict=1)

		self.coated_qty = flt(production_data[0].coated_qty) if production_data else 0
		last_stock_entry_date = flt(production_data[0].actual_end_date) if production_data else 0

		self.per_coated = flt(self.coated_qty / self.stock_qty * 100 if self.stock_qty else 0, 3)

		# Set coating status
		if self.docstatus == 1:
			under_production_allowance = flt(frappe.db.get_single_value("Manufacturing Settings", "under_production_allowance"))
			min_coating_qty = flt(self.stock_qty - (self.stock_qty * under_production_allowance / 100), self.precision("qty"))

			if self.coated_qty and (self.coated_qty >= min_coating_qty or self.status == "Stopped"):
				self.coating_status = "Coated"
			elif self.status == "Stopped":
				self.coating_status = "Not Applicable"
			else:
				self.coating_status = "To Coat"
		else:
			self.coating_status = "Not Applicable"

		self.actual_end_date = last_stock_entry_date if self.coating_status in ["Coated", "Stopped"] else None

		if update:
			self.db_set({
				'coated_qty': self.coated_qty,
				'per_coated': self.per_coated,
				'coating_status': self.coating_status,
				'actual_end_date': self.actual_end_date,
			}, update_modified=update_modified)

	def validate_coating_order_qty(self, from_doctype=None):
		self.validate_completed_qty_for_row(self, 'coated_qty', 'stock_qty',
			allowance_type="production", from_doctype=from_doctype, item_field="fabric_item")

	def has_stock_entry(self):
		return frappe.db.get_value("Stock Entry", {"coating_order": self.name, "docstatus": 1})

	def get_conversion_factor(self):
		conversion_factors = get_textile_conversion_factors()
		uom_to_convert = self.uom + '_to_' + self.stock_uom
		uom_to_convert = uom_to_convert.lower()
		conversion_factor = flt(conversion_factors[uom_to_convert]) or 1
		return conversion_factor


@frappe.whitelist()
def get_fabric_item_details(fabric_item, get_coating_item=True):
	from textile.utils import get_fabric_item_details
	from textile.fabric_printing.doctype.print_process_rule.print_process_rule import get_print_process_values

	out = get_fabric_item_details(fabric_item)

	out.coating_item = None
	out.coating_item_name = None
	if fabric_item and cint(get_coating_item):
		print_process_defaults = get_print_process_values(fabric_item)
		out.coating_item = print_process_defaults.coating_item
		out.coating_item_name = print_process_defaults.coating_item_name

	return out


@frappe.whitelist()
def get_default_coating_bom(coating_item, throw=False):
	coating_bom = None

	if coating_item:
		filters = {"item": coating_item, "is_default": 1}
		coating_bom = frappe.db.get_value("BOM", filters)

		if not coating_bom:
			variant_of = frappe.db.get_value("Item", coating_item, "variant_of")

			if variant_of:
				filters['item'] = variant_of
				coating_bom = frappe.db.get_value("BOM", filters)

	if not coating_bom and cint(throw):
		frappe.throw(_("Default BOM for {0} not found").format(frappe.get_desk_link("Item", coating_item)))

	return coating_bom


@frappe.whitelist()
def stop_unstop(coating_order, status):
	""" Called from client side on Stop/Unstop event"""

	if not frappe.has_permission("Coating Order", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc = frappe.get_doc("Coating Order", coating_order)
	doc.set_status(status)
	doc.set_coating_status(update=True)
	doc.set_status(status, update=True)
	doc.notify_update()

	frappe.msgprint(_("Coating Order has been {0}").format(frappe.bold(status)))

	return doc.status


@frappe.whitelist()
def make_stock_entry_from_coating_order(coating_order_id, qty):
	caoting_order_doc = frappe.get_doc("Coating Order", coating_order_id)
	stock_entry = frappe.new_doc("Stock Entry")

	stock_entry.purpose = "Manufacture"
	stock_entry.company = caoting_order_doc.company
	stock_entry.coating_order = caoting_order_doc.name
	stock_entry.bom_no = caoting_order_doc.coating_bom
	stock_entry.from_bom = 1
	stock_entry.use_multi_level_bom = 1
	stock_entry.fg_completed_qty = flt(qty)
	stock_entry.to_warehouse = caoting_order_doc.fg_warehouse

	stock_entry.set_stock_entry_type()
	stock_entry.get_items()

	if frappe.db.get_single_value("Manufacturing Settings", "auto_submit_manufacture_entry"):
		try:
			ste_copy = frappe.get_doc(copy.deepcopy(stock_entry))
			ste_copy.submit()
			stock_entry = ste_copy
			frappe.msgprint(_("{0} submitted successfully for Coating ({1} {2})").format(
				frappe.get_desk_link("Stock Entry", ste_copy.name),
				stock_entry.get_formatted("fg_completed_qty"),
				caoting_order_doc.stock_uom,
			), indicator="green")

		except OverAllowanceError:
			raise

		except frappe.ValidationError:
			frappe.db.rollback()

	return stock_entry.as_dict()
