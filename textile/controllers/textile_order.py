import frappe
from frappe import _
from frappe.utils import getdate, cstr, flt, cint, clean_whitespace
from erpnext.utilities.transaction_base import TransactionBase
from erpnext.accounts.party import validate_party_frozen_disabled
from textile.utils import validate_textile_item, gsm_to_grams, is_internal_customer
from erpnext.stock.get_item_details import get_bin_details, is_item_uom_convertible


class TextileOrder(TransactionBase):
	def set_fabric_title(self, fabric_material, qty):
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

	def clean_remarks(self):
		fields = ['remarks', 'notes', 'po_no']
		for f in fields:
			if self.meta.has_field(f):
				self.set(f, clean_whitespace(self.get(f)))

	def validate_dates(self):
		self.validate_delivery_date()

		if self.get("po_date") and self.get("delivery_date") and getdate(self.delivery_date) < getdate(self.po_date):
			frappe.throw(_("Planned Delivery Date cannot be before Customer's Purchase Order Date"))

		if self.get("planned_end_date") and getdate(self.planned_end_date) < getdate(self.transaction_date):
			frappe.throw(_("Planned End Date cannot be before Order Date"))

	def validate_delivery_date(self):
		if not self.meta.has_field("delivery_date"):
			return

		if self.meta.has_field("items"):
			items_meta = frappe.get_meta(self.meta.get_field("items").options)
			has_item_wise_delivery_date = items_meta.has_field("delivery_date")
		else:
			has_item_wise_delivery_date = False

		# Set delivery date from items
		if has_item_wise_delivery_date:
			item_delivery_dates = [getdate(d.delivery_date) for d in self.get("items") if d.delivery_date]
			max_item_delivery_date = max(item_delivery_dates) if item_delivery_dates else None

			if max_item_delivery_date and (not self.delivery_date or getdate(self.delivery_date) != max_item_delivery_date):
				self.delivery_date = max_item_delivery_date

		# Validate parent delivery date
		if self.get("delivery_date"):
			if getdate(self.delivery_date) < getdate(self.transaction_date):
				frappe.throw(_("Planned Delivery Date cannot be before Order Date"))

		# Validate items delivery date
		if has_item_wise_delivery_date:
			for d in self.get("items"):
				if not d.delivery_date and self.delivery_date:
					d.delivery_date = self.delivery_date

				if d.delivery_date and getdate(d.delivery_date) < getdate(self.transaction_date):
					frappe.throw(_("Row #{0}: Planned Delivery Date cannot be before Order Date").format(d.idx))

	def validate_customer(self):
		if self.get("customer"):
			validate_party_frozen_disabled("Customer", self.customer)

		self.validate_is_internal_customer()

	def validate_is_internal_customer(self):
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

	def get_fabric_stock_qty(self, fabric_item, fabric_warehouse):
		if not (fabric_item and fabric_warehouse):
			return 0

		bin_details = get_bin_details(fabric_item, fabric_warehouse)
		return flt(bin_details.get("actual_qty"))

	@staticmethod
	def add_fabric_components_to_bom(bom_doc, components, fabric_gsm, fabric_width, fabric_per_pickup):
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

			if not component.do_not_validate_bom:
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
		if not frappe.db.get_value("Item", item_code, "is_stock_item", cache=1):
			return

		default_bom = frappe.db.get_value("Item", item_code, "default_bom", cache=1)
		if not default_bom:
			frappe.throw(_("Could not create BOM because {0} does not have a Default BOM").format(
				frappe.get_desk_link("Item", item_code)
			))

	def get_production_progress_data(self, reference_fieldname, total_qty, uom, item_codes=None):
		item_conditions = ""
		if item_codes:
			item_conditions += " and wo.production_item in %(item_codes)s"

		args = {"name": self.name, "item_codes": item_codes}

		totals = frappe.db.sql(f"""
			select
				sum(wo.qty) as qty,
				sum(wo.producible_qty) as producible_qty,
				sum(wo.material_transferred_for_manufacturing) as material_transferred_for_manufacturing,
				sum(wo.completed_qty) as completed_qty,
				sum(wo.produced_qty) as produced_qty,
				sum(wo.process_loss_qty) as process_loss_qty,
				sum(wo.subcontract_order_qty) as subcontract_order_qty,
				sum(wo.subcontract_received_qty) as subcontract_received_qty,
				sum(wo.packed_qty) as packed_qty,
				sum(wo.rejected_qty) as rejected_qty,
				sum(wo.reconciled_qty) as reconciled_qty
			from `tabWork Order` wo
			where wo.`{reference_fieldname}` = %(name)s and wo.docstatus = 1 {item_conditions}
		""", args, as_dict=1)

		totals = totals[0] if totals else frappe._dict()
		progress_data = frappe._dict({
			"qty": flt(totals.qty) or flt(total_qty),
			"stock_uom": cstr(uom),
			"producible_qty": flt(totals.producible_qty),
			"material_transferred_for_manufacturing": flt(totals.material_transferred_for_manufacturing),
			"completed_qty": flt(totals.completed_qty),
			"produced_qty": flt(totals.produced_qty),
			"process_loss_qty": flt(totals.process_loss_qty),
			"subcontract_order_qty": flt(totals.subcontract_order_qty),
			"subcontract_received_qty": flt(totals.subcontract_received_qty),
			"packed_qty": flt(totals.packed_qty),
			"rejected_qty": flt(totals.rejected_qty),
			"reconciled_qty": flt(totals.reconciled_qty),
			"operations": []
		})

		operations_data = frappe.db.sql(f"""
			select
				woo.operation,
				sum(woo.completed_qty) as completed_qty,
				sum(woo.process_loss_qty) as process_loss_qty,
				sum(woo.previous_loss_qty) as previous_loss_qty
			from `tabWork Order Operation` woo
			inner join `tabWork Order` wo on wo.name = woo.parent
			where wo.`{reference_fieldname}` = %(name)s and wo.docstatus = 1 {item_conditions}
			group by woo.operation
			order by woo.idx
		""", args, as_dict=1)

		for row in operations_data:
			progress_data["operations"].append(row)

		return progress_data
