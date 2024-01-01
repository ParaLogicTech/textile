# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, cstr


def execute(filters=None):
	return FabricPrintingSummary(filters).run()


class FabricPrintingSummary:
	transaction_fields = [
			"received_qty",
			"no_of_orders",
			"ordered_qty",
			"no_of_orders_produced",
			"produced_qty",
			"no_of_orders_packed",
			"packed_qty",
			"no_of_orders_delivered",
			"delivered_qty",
		]

	sum_fields = transaction_fields + [
			"fabrics_created",
			"customer_fabric_qty",
			"own_fabric_qty",
			"total_fabric_qty",
		]

	zero_fields = frappe._dict({field: 0 for field in sum_fields})

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.from_date = getdate(self.filters.from_date)
		self.filters.to_date = getdate(self.filters.to_date)

		if self.filters.from_date > self.filters.to_date:
			frappe.throw(_("Date Range is incorrect"))

	def run(self):
		self.get_data()
		self.get_grouped_data()
		self.get_most_produced_items()
		self.prepare_data()
		self.get_columns()

		return self.columns, self.data

	def get_data_for_digest(self):
		self.get_data()
		self.get_grouped_data()
		self.get_most_produced_items()
		totals_row = self.get_totals_row()

		return self.grouped_data, totals_row

	def get_data(self):
		self.order_data = frappe.db.sql("""
			SELECT item.fabric_material,
				SUM(poi.stock_print_length) AS ordered_qty,
				COUNT(distinct pro.name) AS no_of_orders
			FROM `tabPrint Order Item` poi
			INNER JOIN `tabPrint Order` pro ON pro.name = poi.parent
			INNER JOIN `tabItem` item ON item.name = pro.fabric_item
			WHERE pro.docstatus = 1
				AND pro.transaction_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.fabric_received_data = frappe.db.sql("""
			SELECT item.fabric_material,
				SUM(sle.actual_qty) as received_qty
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` item on item.name = sle.item_code
			LEFT JOIN `tabStock Entry` ste on sle.voucher_type = 'Stock Entry' and sle.voucher_no = ste.name
			WHERE sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND item.textile_item_type IN ('Greige Fabric', 'Ready Fabric')
				AND sle.voucher_type IN ('Purchase Receipt', 'Purchase Invoice', 'Stock Entry')
				AND (sle.voucher_type != 'Stock Entry' OR ste.purpose = 'Material Receipt') 
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.production_data = frappe.db.sql("""
			SELECT item.fabric_material,
				SUM(se.fg_completed_qty) AS produced_qty,
				COUNT(distinct wo.print_order) AS no_of_orders_produced
			FROM `tabStock Entry` se
			INNER JOIN `tabWork Order` wo ON wo.name = se.work_order
			INNER JOIN `tabItem` item ON item.name = wo.fabric_item
			WHERE se.docstatus = 1
				AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND se.purpose = 'Manufacture'
				AND ifnull(wo.print_order, '') != ''
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.packing_data = frappe.db.sql("""
			SELECT item.fabric_material,
				SUM(psi.stock_qty) AS packed_qty,
				COUNT(distinct psi.print_order) AS no_of_orders_packed
			FROM `tabPacking Slip Item` psi
			INNER JOIN `tabPacking Slip` ps ON ps.name = psi.parent
			INNER JOIN `tabItem` item ON item.name = psi.item_code
			WHERE ps.docstatus = 1
				AND ps.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND ifnull(psi.print_order, '') != ''
				AND ifnull(psi.source_packing_slip, '') = ''
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.delivery_data = frappe.db.sql("""
			SELECT item.fabric_material,
				SUM(dni.stock_qty) AS delivered_qty,
				COUNT(distinct dni.print_order) AS no_of_orders_delivered
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			INNER JOIN `tabItem` item ON item.name = dni.item_code
			WHERE dn.docstatus = 1
				AND dn.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND dn.is_return = 0
				AND ifnull(dni.print_order, '') != ''
				AND dni.is_return_fabric = 0
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.fabrics_created = frappe.db.sql("""
			SELECT item.fabric_material, COUNT(*) as fabrics_created
			FROM `tabItem` item
			WHERE item.textile_item_type in ('Ready Fabric', 'Greige Fabric')
				and item.creation BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		wip_warehouses = []

		printing_wip_warehouse = frappe.db.get_single_value("Fabric Printing Settings", "default_printing_wip_warehouse")
		if printing_wip_warehouse:
			wip_warehouses.append(printing_wip_warehouse)

		pretreatment_wip_warehouse = frappe.db.get_single_value("Fabric Pretreatment Settings", "default_pretreatment_wip_warehouse")
		if pretreatment_wip_warehouse:
			wip_warehouses.append(pretreatment_wip_warehouse)

		wip_warehouse_condition = ""
		if wip_warehouses:
			wip_warehouse_condition = " and sle.warehouse not in %(wip_warehouses)s"

		self.total_fabric_qty_data = frappe.db.sql(f"""
			SELECT i.fabric_material,
				SUM(CASE WHEN is_customer_provided_item = 1 THEN sle.actual_qty ELSE 0 END) AS customer_fabric_qty,
				SUM(CASE WHEN is_customer_provided_item = 0 THEN sle.actual_qty ELSE 0 END) AS own_fabric_qty,
				SUM(sle.actual_qty) AS total_fabric_qty
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i ON i.name = sle.item_code
			WHERE i.textile_item_type IN ('Ready Fabric', 'Greige Fabric') AND sle.posting_date <= %(to_date)s
				{wip_warehouse_condition}
			GROUP BY i.fabric_material
		""", {"to_date": self.filters.to_date, "wip_warehouses": wip_warehouses}, as_dict=1)

	def get_grouped_data(self):
		data_bank = [
			self.order_data,
			self.fabric_received_data,
			self.production_data,
			self.packing_data,
			self.delivery_data,
			self.fabrics_created,
			self.total_fabric_qty_data,
		]

		self.grouped_data = {}
		for data_list in data_bank:
			for d in data_list:
				self.grouped_data.setdefault(cstr(d.fabric_material), self.zero_fields.copy()).update(d)

		self.fabric_materials = list(self.grouped_data.keys())

	def prepare_data(self):
		if not self.grouped_data:
			self.data = []
			return

		self.data = sorted(list(self.grouped_data.values()), key=lambda d: d.get('fabric_material'))

		totals_row = self.get_totals_row()
		self.data.append(totals_row)

	def get_totals_row(self):
		totals_row = self.zero_fields.copy()
		totals_row.fabric_material = "'Total'"
		totals_row._bold = 1

		for d in self.grouped_data.values():
			for f in self.sum_fields:
				totals_row[f] += d[f]

		totals_row.has_transactions = False
		for d in self.grouped_data.values():
			if not totals_row.has_transactions:
				for key in self.transaction_fields:
					if d.get(key):
						totals_row.has_transactions = True
						break

		if self.most_produced_items.get(None):
			totals_row.update(self.most_produced_items.get(None))

		return totals_row

	def get_most_produced_items(self):
		self.most_produced_items = {}

		for fabric_material in self.fabric_materials:
			filters = self.filters.copy()
			filters['fabric_material'] = fabric_material
			self.most_produced_items[fabric_material] = get_most_produced_item(filters)

		# For Total Row
		filters = self.filters.copy()
		filters.pop("fabric_material", None)
		self.most_produced_items[None] = get_most_produced_item(filters)

		for fabric_material, group_data in self.grouped_data.items():
			if self.most_produced_items.get(fabric_material):
				group_data.update(self.most_produced_items.get(fabric_material))

		return self.most_produced_items

	def get_columns(self):
		self.columns = [
			{
				"label": _("Fabric Material"),
				"fieldname": "fabric_material",
				"fieldtype": "Link",
				"options": "Fabric Material",
				"width": 110
			},
			{
				"label": _("Fabric Received Qty"),
				"fieldname": "received_qty",
				"fieldtype": "Float",
				"width": 125
			},
			{
				"label": _("Orders Received"),
				"fieldname": "no_of_orders",
				"fieldtype": "Int",
				"width": 105
			},
			{
				"label": _("Ordered Qty"),
				"fieldname": "ordered_qty",
				"fieldtype": "Float",
				"width": 105
			},
			{
				"label": _("Orders Produced"),
				"fieldname": "no_of_orders_produced",
				"fieldtype": "Int",
				"width": 108
			},
			{
				"label": _("Produced Qty"),
				"fieldname": "produced_qty",
				"fieldtype": "Float",
				"width": 105
			},
			{
				"label": _("Orders Packed"),
				"fieldname": "no_of_orders_produced",
				"fieldtype": "Int",
				"width": 105
			},
			{
				"label": _("Packed Qty"),
				"fieldname": "packed_qty",
				"fieldtype": "Float",
				"width": 105
			},
			{
				"label": _("Orders Delivered"),
				"fieldname": "no_of_orders_delivered",
				"fieldtype": "Int",
				"width": 108
			},
			{
				"label": _("Delivered Qty"),
				"fieldname": "delivered_qty",
				"fieldtype": "Float",
				"width": 105
			},
			{
				"label": _("Total Fabric Stock"),
				"fieldname": "total_fabric_qty",
				"fieldtype": "Float",
				"width": 115,
			},
			{
				"label": _("Customer Fabric Stock"),
				"fieldname": "customer_fabric_qty",
				"fieldtype": "Float",
				"width": 135,
			},
			{
				"label": _("Own Fabric Stock"),
				"fieldname": "own_fabric_qty",
				"fieldtype": "Float",
				"width": 110,
			},
			{
				"label": _("Fabrics Created"),
				"fieldname": "fabrics_created",
				"fieldtype": "Int",
				"width": 100
			},
			{
				"label": _("Top Item Code"),
				"fieldname": "most_produced_item",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100,
			},
			{
				"label": _("Top Item Name"),
				"fieldname": "most_produced_item_name",
				"fieldtype": "Data",
				"width": 200,
			},
			{
				"label": _("Top Item Produced Qty"),
				"fieldname": "most_produced_qty",
				"fieldtype": "Float",
				"width": 140,
			},
			{
				"label": _("Top Item's Customer"),
				"fieldname": "most_produced_item_customer",
				"fieldtype": "Link",
				"options": "Customer",
				"width": 200,
			},
		]


def get_most_produced_item(filters):
	if not filters:
		filters = {}

	conditions = []

	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
	if filters.get("fabric_material"):
		conditions.append("item.fabric_material = %(fabric_material)s")

	conditions = " and {0}".format(" and ".join(conditions)) if conditions else ""

	most_produced = frappe.db.sql(f"""
		SELECT SUM(se.fg_completed_qty) AS most_produced_qty,
			wo.production_item as most_produced_item,
			item.item_name as most_produced_item_name,
			item.fabric_item as most_produced_item_fabric,
			item.fabric_item_name as most_produced_item_fabric_name,
			item.image as most_produced_item_image,
			item.customer as most_produced_item_customer
		FROM `tabStock Entry` se
		INNER JOIN `tabWork Order` wo ON wo.name = se.work_order
		INNER JOIN `tabItem` item ON item.name = wo.production_item
		WHERE se.docstatus = 1
			AND se.purpose = 'Manufacture'
			AND ifnull(wo.print_order, '') != ''
			{conditions}
		GROUP BY most_produced_item
		HAVING most_produced_qty > 0
		ORDER BY most_produced_qty DESC
		LIMIT 1
	""", filters, as_dict=1)

	return most_produced[0] if most_produced else None
