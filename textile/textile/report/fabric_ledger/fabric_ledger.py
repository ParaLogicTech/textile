# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from textile.utils import get_combined_fabric_items


def execute(filters=None):
	return FabricLedger(filters).run()


class FabricLedger:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.show_item_name = frappe.defaults.get_global_default('item_naming_by') != "Item Name"
		self.show_customer_name = frappe.defaults.get_global_default('cust_master_name') == "Naming Series"
		self.has_batches = False

	def run(self):
		self.validate_filters()
		self.get_items()
		self.get_data()
		self.prepare_rows()
		self.get_columns()

		return self.columns, self.rows

	def validate_filters(self):
		if self.filters.item_code:
			textile_item_type = frappe.db.get_value("Item", self.filters.item_code, "textile_item_type")
			if textile_item_type not in ("Greige Fabric", "Ready Fabric"):
				frappe.throw(_("Item must be Greige Fabric or Ready Fabric"))

		self.filters.rejected_warehouses = frappe.get_all("Warehouse", filters={
			"is_group": 0, "stock_type": "Rejected"
		}, pluck="name")

		self.filters.shrinkage_stock_entry_type = frappe.db.get_single_value("Fabric Printing Settings", "stock_entry_type_for_fabric_shrinkage")

	def get_items(self):
		self.ready_fabric_items = []
		self.greige_fabric_items = []
		self.printed_fabric_items = []

		if self.filters.item_code:
			fabrics = get_combined_fabric_items(self.filters.item_code,
				combine_greige_ready=self.filters.combine_greige_ready)

			self.ready_fabric_items = fabrics.ready_fabric_items
			self.greige_fabric_items = fabrics.greige_fabric_items
			self.printed_fabric_items = fabrics.printed_fabric_items

		elif self.filters.customer:
			self.ready_fabric_items = frappe.get_all("Item", filters={
				"customer": self.filters.customer, "textile_item_type": "Ready Fabric"
			}, pluck="name")
			self.greige_fabric_items = frappe.get_all("Item", filters={
				"customer": self.filters.customer, "textile_item_type": "Greige Fabric"
			}, pluck="name")
			self.printed_fabric_items = frappe.get_all("Item", filters={
				"customer": self.filters.customer, "textile_item_type": "Printed Design"
			}, pluck="name")

		self.filters.fabric_item_codes = list(set(self.greige_fabric_items + self.ready_fabric_items + self.printed_fabric_items))

	def get_data(self):
		self.data = []
		self.opening_qty = None
		self.opening_packed_qty = None

		if not self.filters.fabric_item_codes:
			return

		conditions = self.get_conditions()

		if self.filters.from_date:
			rejected_warehouse_condition = "and sle.warehouse not in %(rejected_warehouses)s"\
				if self.filters.rejected_warehouses else ""

			self.opening_qty = frappe.db.sql(f"""
				select sum(sle.actual_qty)
				from `tabStock Ledger Entry` sle
				where sle.item_code in %(fabric_item_codes)s
					and sle.posting_date < %(from_date)s
					{rejected_warehouse_condition}
			""", self.filters)

			self.opening_packed_qty = frappe.db.sql(f"""
				select sum(sle.actual_qty)
				from `tabStock Ledger Entry` sle
				where sle.item_code in %(fabric_item_codes)s
					and (sle.packing_slip is not null and sle.packing_slip != '')
					and sle.posting_date < %(from_date)s
					{rejected_warehouse_condition}
			""", self.filters)

			self.opening_qty = flt(self.opening_qty[0][0]) if self.opening_qty else 0
			self.opening_packed_qty = flt(self.opening_packed_qty[0][0]) if self.opening_packed_qty else 0

		self.data = frappe.db.sql(f"""
			select sle.posting_date,
				sle.voucher_type, sle.voucher_no,
				sle.item_code, item.item_name,
				sle.warehouse, sle.batch_no, sle.packing_slip,
				sle.party_type, sle.party,
				item.textile_item_type,
				fabric_item.name as fabric_item, fabric_item.item_name as fabric_item_name,
				sle.actual_qty, sle.stock_uom as uom,
				ste.purpose, ste.stock_entry_type, ste.work_order, ste.coating_order,
				ste.print_order as ste_print_order, ste.pretreatment_order as ste_pretreatment_order,
				dni.print_order as dni_print_order, dni.pretreatment_order as dni_pretreatment_order,
				psi.print_order as psi_print_order, psi.pretreatment_order as psi_pretreatment_order
			from `tabStock Ledger Entry` sle
			inner join `tabItem` item on sle.item_code = item.name
			left join `tabItem` fabric_item on fabric_item.name = item.fabric_item
			left join `tabStock Entry` ste on ste.name = sle.voucher_no and sle.voucher_type = 'Stock Entry'
			left join `tabDelivery Note Item` dni on dni.name = sle.voucher_detail_no and sle.voucher_type = 'Delivery Note'
			left join `tabPacking Slip Item` psi on psi.name = sle.voucher_detail_no and sle.voucher_type = 'Packing Slip'
			where sle.item_code in %(fabric_item_codes)s
				{conditions}
			order by sle.posting_date, sle.posting_time, sle.creation
		""", self.filters, as_dict=1)

	def get_conditions(self):
		conditions = []

		if self.filters.company:
			conditions.append("sle.company = %(company)s")

		if self.filters.from_date:
			conditions.append("sle.posting_date >= %(from_date)s")

		if self.filters.to_date:
			conditions.append("sle.posting_date <= %(to_date)s")

		if self.filters.batch_no:
			conditions.append("sle.batch_no = %(batch_no)s")

		return "AND {}".format(" AND ".join(conditions)) if conditions else ""

	def prepare_rows(self):
		self.rows = []

		# Preprocess Data
		for sle in self.data:
			sle["disable_item_formatter"] = 1

			if sle.textile_item_type != "Printed Design":
				sle.fabric_item = sle.item_code
				sle.fabric_item_name = sle.item_name

			sle.document_type = sle.voucher_type
			sle.document_no = sle.voucher_no
			if sle.ste_print_order and self.filters.merge_print_production and sle.purpose == "Manufacture":
				sle.document_type = "Print Order"
				sle.document_no = sle.ste_print_order

			sle.print_order = sle.ste_print_order or sle.dni_print_order or sle.psi_print_order
			sle.pretreatment_order = sle.ste_pretreatment_order or sle.dni_pretreatment_order or sle.psi_pretreatment_order

			if sle.print_order:
				sle.order_type = "Print Order"
				sle.order_no = sle.print_order
			elif sle.pretreatment_order:
				sle.order_type = "Pretreatment Order"
				sle.order_no = sle.pretreatment_order
			elif sle.coating_order:
				sle.order_type = "Coating Order"
				sle.order_no = sle.coating_order

			sle.is_rejection = 1 if sle.warehouse in self.filters.rejected_warehouses else 0

		# Group rows by voucher and fabric item
		voucher_map = {}
		for sle in self.data:
			voucher_key = (sle.posting_date, sle.document_type, sle.document_no)
			voucher_dict = voucher_map.setdefault(voucher_key, frappe._dict({
				"actual_qty": 0, "packed_qty": 0, "fabric_items": {}
			}))

			row = voucher_dict.fabric_items.get(sle.fabric_item)
			if not row:
				row = voucher_map[voucher_key].fabric_items[sle.fabric_item] = sle.copy()
				row.actual_qty = 0
				row.in_qty = 0
				row.out_qty = 0
				row.rejected_qty = 0
				row.packed_qty = 0

			voucher_dict.actual_qty += sle.actual_qty
			row.actual_qty += sle.actual_qty

			packed_qty = sle.actual_qty if sle.packing_slip else 0
			voucher_dict.packed_qty += packed_qty
			row.packed_qty += packed_qty

			if sle.is_rejection:
				row.rejected_qty += sle.actual_qty

			if flt(sle.actual_qty) >= 0:
				row.in_qty += sle.actual_qty
			else:
				row.out_qty += -sle.actual_qty

		# Opening Row
		opening_row = frappe._dict()
		if self.opening_qty is not None:
			opening_row = self.get_opening_row()
			self.rows.append(opening_row)

		# Movement Rows
		movement_rows = []
		accumulated_balance_qty = opening_row.qty_after_transaction or 0
		accumulated_packed_qty = opening_row.packed_qty_after_transaction or 0

		for voucher_dict in voucher_map.values():
			for row in voucher_dict.fabric_items.values():
				row.is_internal_entry = not flt(voucher_dict.actual_qty, 6) or not flt(row.actual_qty, 6)
				row.is_packing_entry = flt(voucher_dict.packed_qty, 6) or flt(row.packed_qty, 6)

				accumulated_balance_qty += row.actual_qty
				accumulated_packed_qty += row.packed_qty
				row.qty_after_transaction = accumulated_balance_qty
				row.packed_qty_after_transaction = accumulated_packed_qty

				if row.rejected_qty > 0:
					row.in_qty -= row.rejected_qty
					row.out_qty -= row.rejected_qty
				elif row.rejected_qty < 0:
					row.in_qty += row.rejected_qty
					row.out_qty += row.rejected_qty

				skip_row = False
				if row.is_internal_entry and self.filters.hide_internal_entries:
					skip_row = True
				if row.rejected_qty and not flt(row.in_qty, 6) and not flt(row.out_qty, 6):
					skip_row = True

				if not skip_row:
					movement_rows.append(row)

				if row.rejected_qty:
					rejected_row = row.copy()
					rejected_row.is_internal_entry = False
					rejected_row.is_wastage = True

					if rejected_row.rejected_qty > 0:
						rejected_row.in_qty = 0
						rejected_row.out_qty = rejected_row.rejected_qty
					else:
						rejected_row.in_qty = -rejected_row.rejected_qty
						rejected_row.out_qty = 0

					rejected_row.actual_qty = -rejected_row.rejected_qty
					accumulated_balance_qty += rejected_row.actual_qty
					rejected_row.qty_after_transaction = accumulated_balance_qty

					if rejected_row.packing_slip:
						rejected_row.packed_qty = -rejected_row.rejected_qty
						accumulated_packed_qty += rejected_row.packed_qty
						rejected_row.packed_qty_after_transaction = accumulated_packed_qty

					movement_rows.append(rejected_row)

		# Entry Type
		for row in movement_rows:
			if row.is_wastage:
				row.entry_type = "Wastage"
			elif row.purpose:
				if row.purpose == "Manufacture":
					if row.print_order:
						row.entry_type = "Printing"
					elif row.pretreatment_order:
						row.entry_type = "Pretreatment"
					elif row.coating_order:
						row.entry_type = "Coating"
					else:
						row.entry_type = "Production"
				elif row.purpose == "Material Receipt":
					row.entry_type = "Fabric Receipt"
				elif row.purpose == "Material Transfer for Manufacture":
					row.entry_type = "Transfer to Production"
				elif row.purpose == "Material Issue":
					if self.filters.shrinkage_stock_entry_type and row.stock_entry_type == self.filters.shrinkage_stock_entry_type:
						row.entry_type = "Shrinkage"
					else:
						row.entry_type = "Reconciliation"
				else:
					row.entry_type = row.purpose
			elif row.voucher_type == "Delivery Note":
				row.entry_type = "Delivery"
			elif row.voucher_type == "Packing Slip":
				row.entry_type = "Packing"
			elif row.voucher_type == "Stock Reconciliation":
				row.entry_type = "Reconciliation"
			elif row.voucher_type == "Purchase Receipt":
				row.entry_type = "Purchase"
			else:
				row.entry_type = row.voucher_type

		self.rows += movement_rows

		# Totals
		total_in_qty = 0
		total_out_qty = 0
		for row in self.rows:
			if not row.is_internal_entry:
				total_in_qty += flt(row.in_qty)
				total_out_qty += flt(row.out_qty)

			if row.batch_no:
				self.has_batches = True

		# Closing Row
		if self.opening_qty is not None:
			self.rows.append(self.get_closing_row(accumulated_balance_qty, accumulated_packed_qty, total_in_qty, total_out_qty))

	def get_opening_row(self):
		return frappe._dict({
			"posting_date": self.filters.from_date,
			"entry_type": "Opening Stock",
			"fabric_item": self.filters.item_code,
			"fabric_item_name": frappe.db.get_value("Item", self.filters.item_code, "item_name", cache=1),
			"uom": frappe.db.get_value("Item", self.filters.item_code, "stock_uom", cache=1),
			"qty_after_transaction": self.opening_qty or 0,
			"packed_qty_after_transaction": self.opening_packed_qty or 0,
			"is_opening": True,
			"_bold": True,
		})

	def get_closing_row(self, closing_qty, packed_qty, in_qty, out_qty):
		return frappe._dict({
			"posting_date": self.filters.to_date,
			"entry_type": "Closing Stock",
			"fabric_item": self.filters.item_code,
			"fabric_item_name": frappe.db.get_value("Item", self.filters.item_code, "item_name", cache=1),
			"uom": frappe.db.get_value("Item", self.filters.item_code, "stock_uom", cache=1),
			"in_qty": in_qty,
			"out_qty": out_qty,
			"qty_after_transaction": closing_qty,
			"packed_qty_after_transaction": packed_qty,
			"is_closing": True,
			"_bold": True,
		})

	def get_columns(self):
		columns = [
			{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
			{"label": _("Entry Type"), "fieldname": "entry_type", "fieldtype": "Data", "width": 120},
			{"label": _("Fabric Item"), "fieldname": "fabric_item", "fieldtype": "Link", "options": "Item", "width": 100, "align": "left"},
			{"label": _("Fabric Name"), "fieldname": "fabric_item_name", "fieldtype": "Data", "width": 220, "align": "left"},
			{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 60},
			{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 80},
			{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 80},
			{"label": _("Packed Qty"), "fieldname": "packed_qty_after_transaction", "fieldtype": "Float", "width": 100},
			{"label": _("Balance Qty"), "fieldname": "qty_after_transaction", "fieldtype": "Float", "width": 100},
			{"label": _("Party"), "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 150},
			{"label": _("Voucher Type"), "fieldname": "document_type", "width": 120},
			{"label": _("Voucher #"), "fieldname": "document_no", "fieldtype": "Dynamic Link", "options": "document_type", "width": 120},
			{"label": _("Order Type"), "fieldname": "order_type", "fieldtype": "Data", "width": 120},
			{"label": _("Order #"), "fieldname": "order_no", "fieldtype": "Dynamic Link", "options": "order_type", "width": 120},
			{"label": _("Batch No"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 150},
		]

		if not self.has_batches:
			columns = [c for c in columns if c.get("fieldname") != "batch_no"]

		self.columns = columns
