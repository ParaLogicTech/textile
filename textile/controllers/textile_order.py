import frappe
from frappe import _
from frappe.utils import getdate, cstr, flt, cint
from erpnext.controllers.status_updater import StatusUpdater
from erpnext.accounts.party import validate_party_frozen_disabled
from textile.utils import validate_textile_item, gsm_to_grams, is_internal_customer
from erpnext.stock.get_item_details import get_bin_details, is_item_uom_convertible


class TextileOrder(StatusUpdater):
	def set_title(self, fabric_material, qty):
		fabric_material_abbr = None
		if fabric_material:
			fabric_material_abbr = frappe.get_cached_value("Fabric Material", fabric_material, "abbreviation")

		customer_name = cstr(self.customer_name or self.customer)
		customer_name = customer_name[:20]

		self.title = "{0} {1} {2} m".format(
			customer_name,
			fabric_material_abbr or "Xx",
			cint(flt(qty, 0))
		)

	def validate_dates(self):
		if self.get("delivery_date"):
			if self.get("transaction_date") and getdate(self.delivery_date) < getdate(self.transaction_date):
				frappe.throw(_("Planned Delivery Date cannot be before Order Date"))

			if self.get("po_date") and getdate(self.delivery_date) < getdate(self.po_date):
				frappe.throw(_("Planned Delivery Date cannot be before Customer's Purchase Order Date"))

	def validate_customer(self):
		if self.get("customer"):
			validate_party_frozen_disabled("Customer", self.customer)

		if self.meta.has_field("is_internal_customer"):
			self.is_internal_customer = is_internal_customer(self.customer, self.company)

			if self.is_internal_customer:
				if self.meta.has_field("delivery_required"):
					self.delivery_required = 0
				if self.meta.has_field("is_fabric_provided_by_customer"):
					self.is_fabric_provided_by_customer = 0

	def validate_pretreatment_order(self):
		if not self.get("pretreatment_order"):
			return

		pretreatment_order = frappe.db.get_value("Pretreatment Order", self.pretreatment_order,
			["customer", "ready_fabric_item", "fg_warehouse", "docstatus", "status", "is_internal_customer"],
			as_dict=1)

		if not pretreatment_order:
			frappe.throw(_("Pretreatment Order {0} does not exist").format(
				frappe.bold(self.pretreatment_order)
			))

		if pretreatment_order.docstatus != 1:
			frappe.throw(_("{0} is not submitted").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order)
			))
		if pretreatment_order.status == "Closed":
			frappe.throw(_("{0} is {1}").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order),
				pretreatment_order.status)
			)
		if pretreatment_order.is_internal_customer:
			frappe.throw(_("{0} is for an internal customer").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order))
			)

		if self.customer != pretreatment_order.customer:
			frappe.throw(_("Customer does not match with {0}. Customer should be {1}").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order),
				frappe.bold(pretreatment_order.customer)
			))
		if self.fabric_item != pretreatment_order.ready_fabric_item:
			frappe.throw(_("Ready Fabric Item does not match with {0}. Fabric Item should be {1}").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order),
				frappe.bold(pretreatment_order.ready_fabric_item)
			))
		if self.fabric_warehouse != pretreatment_order.fg_warehouse:
			frappe.throw(_("Fabric Warehouse does not match with {0}'s Finished Goods Warehouse. Fabric Warehouse should be {1}").format(
				frappe.get_desk_link("Pretreatment Order", self.pretreatment_order),
				frappe.bold(pretreatment_order.fg_warehouse)
			))

	def validate_fabric_item(self, textile_item_type, prefix=None):
		fabric_field = f"{cstr(prefix)}fabric_item"
		fabric_item = self.get(fabric_field)
		fabric_label = self.meta.get_label(fabric_field)

		if fabric_item:
			validate_textile_item(fabric_item, textile_item_type)

			if self.get("is_fabric_provided_by_customer"):
				item_details = frappe.get_cached_value("Item", fabric_item,
					["is_customer_provided_item", "customer"], as_dict=1)

				if not item_details.is_customer_provided_item:
					frappe.throw(_("{0} {1} is not a Customer Provided Item").format(
						fabric_label, frappe.bold(self.fabric_item)
					))

				if item_details.customer != self.customer:
					frappe.throw(_("Customer Provided {0} {1} does not belong to Customer {2}").format(
						fabric_label, frappe.bold(fabric_item), frappe.bold(self.customer)
					))

	def set_fabric_stock_qty(self, prefix=None):
		fabric_field = f"{cstr(prefix)}fabric_item"
		qty_field = f"{cstr(prefix)}fabric_stock_qty"
		fabric_item = self.get(fabric_field)

		if not fabric_item or not self.get("fabric_warehouse"):
			self.set(qty_field, 0)
			return

		bin_details = get_bin_details(fabric_item, self.fabric_warehouse)
		self.set(qty_field, flt(bin_details.get("actual_qty")))

	@staticmethod
	def add_components_to_bom(bom_doc, components, fabric_gsm, fabric_width, fabric_per_pickup):
		for component in components:
			if component.consumption_by_fabric_weight:
				bom_qty_precision = frappe.get_precision("BOM Item", "qty")

				if not fabric_width:
					frappe.throw(_("Could not create BOM because Fabric Width is not provided"))
				if not fabric_gsm:
					frappe.throw(_("Could not create BOM because Fabric GSM is not provided"))
				if not fabric_per_pickup:
					frappe.throw(_("Could not create BOM because Fabric Pickup % is not provided"))

				fabric_grams_per_meter = gsm_to_grams(fabric_gsm, fabric_width)
				consumption_grams_per_meter = fabric_grams_per_meter * flt(fabric_per_pickup) / 100

				qty = flt(consumption_grams_per_meter, bom_qty_precision)
				uom = "Gram"
			else:
				qty = 1
				uom = "Meter"

			TextileOrder.validate_item_has_bom(component.item_code)
			TextileOrder.validate_item_convertible_to_uom(component.item_code, uom)

			bom_doc.append("items", {
				"item_code": component.item_code,
				"qty": qty,
				"uom": uom,
				"skip_transfer_for_manufacture": 1,
			})

	@staticmethod
	def validate_item_convertible_to_uom(item_code, uom):
		def cache_generator():
			return is_item_uom_convertible(item_code, uom)

		is_convertible = frappe.local_cache("textile_order_item_convertible_to_uom", (item_code, uom), cache_generator)
		if not is_convertible:
			frappe.throw(_("Could not create BOM because {0} is not convertible to {1}").format(
				frappe.get_desk_link("Item", item_code), uom
			))

	@staticmethod
	def validate_item_has_bom(item_code):
		if frappe.db.get_value("Item", item_code, "is_stock_item", cache=1):
			return

		default_bom = frappe.db.get_value("Item", item_code, "default_bom", cache=1)
		if not default_bom:
			frappe.throw(_("Could not create BOM because {0} does not have a Default BOM").format(
				frappe.get_desk_link("Item", item_code)
			))
