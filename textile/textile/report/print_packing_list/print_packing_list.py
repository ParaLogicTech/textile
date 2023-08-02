# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr


def execute(filters=None):
	return PrintPackingList(filters).run()


class PrintPackingList:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.show_item_name = frappe.defaults.get_global_default('item_naming_by') != "Item Name"
		self.show_customer_name = frappe.defaults.get_global_default('cust_master_name') == "Naming Series"

	def run(self):
		self.get_data()
		self.prepare_data()
		self.get_columns()

		return self.columns, self.data

	def get_data(self):
		conditions = self.get_conditions()

		self.data = frappe.db.sql("""
			SELECT ps.name as packing_slip, ps.posting_date as packing_date, ps.package_type,
				ps.customer, ps.warehouse, ps.status, psi.print_order, psi.sales_order, psi.work_order,
				psi.stock_qty as qty, psi.stock_uom as uom, psi.item_code, psi.item_name, psi.panel_qty,
				pro.fabric_item, pro.fabric_item_name, item.textile_item_type
			FROM `tabPacking Slip Item` psi
			INNER JOIN `tabPacking Slip` ps
				ON ps.name = psi.parent
			INNER JOIN `tabPrint Order` pro
				ON pro.name = psi.print_order
			INNER JOIN `tabItem` item
				ON item.name = psi.item_code
			WHERE ps.docstatus = 1
				AND ps.status != 'Unpacked'
				AND ifnull(psi.source_packing_slip, '') = ''
				{conditions}
			ORDER BY ps.posting_date, ps.name, psi.idx
		""".format(conditions=conditions), self.filters, as_dict=1)

	def get_conditions(self):
		conditions = []

		if self.filters.company:
			conditions.append("ps.company = %(company)s")

		if self.filters.customer:
			conditions.append("ps.customer = %(customer)s")

		if self.filters.print_order:
			if type(self.filters.print_order) == str:
				self.filters.print_order = cstr(self.filters.print_order).strip()
				self.filters.print_order = [d.strip() for d in self.filters.print_order.split(',') if d]

			conditions.append("psi.print_order in %(print_order)s")

		if self.filters.fabric_item:
			conditions.append("(item.fabric_item = %(fabric_item)s or (item.item_code = %(fabric_item)s))")

		self.filters.delivery_status = ['In Stock']
		if self.filters.show_delivered:
			self.filters.delivery_status.append('Delivered')

		conditions.append("ps.status IN %(delivery_status)s")

		return "AND {}".format(" AND ".join(conditions)) if conditions else ""

	def prepare_data(self):
		for d in self.data:
			d["disable_item_formatter"] = 1

			if not d.panel_qty:
				d.panel_qty = None

			if d.textile_item_type == "Printed Design":
				d.design_item = d.item_code
				d.design_item_name = d.item_name

	def get_columns(self):
		columns = [
			{
				"label": _("Package"),
				"fieldname": "packing_slip",
				"fieldtype": "Link",
				"options": "Packing Slip",
				"width": 80
			},
			{
				"label": _("Date"),
				"fieldname": "packing_date",
				"fieldtype": "Date",
				"width": 85
			},
			{
				"label": _("Package Type"),
				"fieldname": "package_type",
				"fieldtype": "Link",
				"options": "Package Type",
				"width": 100
			},
			{
				"label": _("Customer"),
				"fieldname": "customer",
				"fieldtype": "Link",
				"options": "Customer",
				"width": 80 if self.show_customer_name else 150
			},
			{
				"label": _("Customer Name"),
				"fieldname": "customer_name",
				"fieldtype": "Data",
				"width": 150
			},
			{
				"label": _("Print Order"),
				"fieldname": "print_order",
				"fieldtype": "Link",
				"options": "Print Order",
				"width": 100
			},
			{
				"label": _("Sales Order"),
				"fieldname": "sales_order",
				"fieldtype": "Link",
				"options": "Sales Order",
				"width": 100
			},
			{
				"label": _("Fabric Item"),
				"fieldname": "fabric_item",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100 if self.show_item_name else 150
			},
			{
				"label": _("Fabric Name"),
				"fieldname": "fabric_item_name",
				"fieldtype": "Data",
				"width": 150
			},
			{
				"label": _("Design Item"),
				"fieldname": "design_item",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100 if self.show_item_name else 150
			},
			{
				"label": _("Design Name"),
				"fieldname": "design_item_name",
				"fieldtype": "Data",
				"width": 150
			},
			{
				"label": _("Qty"),
				"fieldname": "qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("UOM"),
				"fieldname": "uom",
				"fieldtype": "Link",
				"options": "UOM",
				"width": 60
			},
			{
				"label": _("Panels"),
				"fieldname": "panel_qty",
				"fieldtype": "Float",
				"precision": 1,
				"width": 80
			},
			{
				"label": _("Status"),
				"fieldname": "status",
				"fieldtype": "Data",
				"width": 80
			},
			{
				"label": _("Work Order"),
				"fieldname": "work_order",
				"fieldtype": "Link",
				"options": "Work Order",
				"width": 100
			},
			{
				"label": _("Warehouse"),
				"fieldname": "warehouse",
				"fieldtype": "Link",
				"options": "Warehouse",
				"width": 120
			},
		]

		if not self.show_customer_name:
			columns = [c for c in columns if c['fieldname'] != 'customer_name']

		if not self.show_item_name:
			columns = [c for c in columns if c['fieldname'] != 'item_name']

		self.columns = columns
