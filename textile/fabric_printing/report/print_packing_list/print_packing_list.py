# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, unscrub
from frappe.utils import cstr, flt, cint
from frappe.desk.query_report import group_report_data


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
		data = self.get_grouped_data()
		self.get_columns()

		skip_total_row = len(self.group_by) > 0

		return self.columns, data, None, None, None, skip_total_row

	def get_data(self):
		conditions = self.get_conditions()

		self.data = frappe.db.sql("""
			SELECT ps.name as packing_slip, ps.posting_date as posting_date, ps.package_type,
				ps.customer, ps.warehouse, ps.status, psi.print_order, psi.sales_order, psi.work_order,
				psi.stock_qty as qty, psi.stock_uom as uom, psi.panel_qty,
				psi.item_code, psi.item_name, psi.is_return_fabric,
				pro.fabric_item, pro.fabric_item_name, item.textile_item_type
			FROM `tabPacking Slip Item` psi
			INNER JOIN `tabPacking Slip` ps ON ps.name = psi.parent
			INNER JOIN `tabPrint Order` pro ON pro.name = psi.print_order
			INNER JOIN `tabItem` item ON item.name = psi.item_code
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
			if isinstance(self.filters.print_order, str):
				self.filters.print_order = cstr(self.filters.print_order).strip()
				self.filters.print_order = [d.strip() for d in self.filters.print_order.split(',') if d]

			conditions.append("psi.print_order in %(print_order)s")

		if self.filters.packing_slip:
			conditions.append("ps.name = %(packing_slip)s")

		if self.filters.package_type:
			conditions.append("ps.package_type = %(package_type)s")

		if self.filters.process_item:
			conditions.append("pro.process_item = %(process_item)s")

		if self.filters.fabric_item:
			conditions.append("(item.fabric_item = %(fabric_item)s or (item.item_code = %(fabric_item)s))")

		if self.filters.fabric_material:
			conditions.append("item.fabric_material = %(fabric_material)s")

		if self.filters.fabric_type:
			conditions.append("item.fabric_type = %(fabric_type)s")

		self.filters.delivery_status = ['In Stock']
		if self.filters.show_delivered:
			self.filters.delivery_status.append('Delivered')

		conditions.append("ps.status IN %(delivery_status)s")

		return "AND {}".format(" AND ".join(conditions)) if conditions else ""

	def prepare_data(self):
		for d in self.data:
			d["disable_item_formatter"] = 1

			d["reference_type"] = "Item"
			d["reference"] = d.item_code

			if not d.panel_qty:
				d.panel_qty = None

			d.total_qty = d.qty
			if d.is_return_fabric:
				d.return_qty = d.qty
				d.qty = None

			if d.textile_item_type == "Printed Design":
				d.design_item = d.item_code
				d.design_item_name = d.item_name
			elif d.is_return_fabric:
				d.design_item_name = "Return Fabric"

	def get_grouped_data(self):
		self.group_by = [None]
		for i in range(2):
			group_label = self.filters.get("group_by_" + str(i + 1), "").replace("Group by ", "")

			if group_label:
				if group_label == "Package":
					self.group_by.append("packing_slip")
				elif group_label == "Design Item":
					self.group_by.append(("design_item", "is_return_fabric"))
				else:
					self.group_by.append(scrub(group_label))

		if len(self.group_by) <= 1:
			return self.data

		return group_report_data(self.data, self.group_by, calculate_totals=self.calculate_group_totals,
			totals_only=self.filters.totals_only, starting_level=0)

	def calculate_group_totals(self, data, group_field, group_value, grouped_by):
		totals = frappe._dict()

		# Copy grouped by into total row
		for f, g in grouped_by.items():
			totals[f] = g

		# Sum
		uoms = set()
		sum_fields = ['qty', 'return_qty', 'total_qty', 'panel_qty']
		for d in data:
			for f in sum_fields:
				totals[f] = flt(totals.get(f)) + flt(d.get(f))

			uoms.add(d.uom)

		if len(uoms) == 1:
			totals.uom = list(uoms)[0]

		group_reference_doctypes = {
			"fabric_item": "Item",
			"design_item": "Item",
		}

		# set reference field
		reference_field = group_field[0] if isinstance(group_field, (list, tuple)) else group_field
		reference_dt = group_reference_doctypes.get(reference_field, unscrub(cstr(reference_field)))

		totals['reference_type'] = reference_dt
		if not group_field:
			totals['reference'] = "'Total'"
		elif not reference_dt:
			totals['reference'] = "'{0}'".format(grouped_by.get(reference_field))
		else:
			totals['reference'] = grouped_by.get(reference_field)

		if not group_field and self.group_by == [None]:
			totals['reference'] = "'Total'"

		totals['disable_item_formatter'] = cint(self.show_item_name)

		if totals.get("print_order"):
			totals['customer'] = data[0].customer
			totals['fabric_item'] = data[0].fabric_item

		if totals.get("packing_slip"):
			totals['package_type'] = data[0].package_type
			totals['posting_date'] = data[0].posting_date
			totals['customer'] = data[0].customer
			totals['status'] = data[0].status
			totals['warehouse'] = data[0].warehouse

			print_orders = set([d.print_order for d in data if d.print_order])
			fabric_items = set([d.fabric_item for d in data if d.fabric_item])
			if len(print_orders) == 1:
				totals['print_order'] = list(print_orders)[0]
			if len(fabric_items) == 1:
				totals['fabric_item'] = list(fabric_items)[0]

		if totals.get("is_return_fabric") and not totals.get("design_item") and not totals.get("reference"):
			totals['design_item_name'] = "Return Fabric"
			totals['reference'] = "'Return Fabric'"

		if totals.get("design_item"):
			totals['design_item_name'] = data[0].design_item_name
			totals['fabric_item'] = data[0].fabric_item

		if totals.get('fabric_item'):
			totals['fabric_item_name'] = data[0].fabric_item_name

		if totals.get('customer'):
			totals['customer_name'] = data[0].customer_name

		return totals

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
				"fieldname": "posting_date",
				"fieldtype": "Date",
				"width": 85
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
				"label": _("UOM"),
				"fieldname": "uom",
				"fieldtype": "Link",
				"options": "UOM",
				"width": 60
			},
			{
				"label": _("Qty"),
				"fieldname": "qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Return"),
				"fieldname": "return_qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Total"),
				"fieldname": "total_qty",
				"fieldtype": "Float",
				"width": 80
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
				"label": _("Package Type"),
				"fieldname": "package_type",
				"fieldtype": "Link",
				"options": "Package Type",
				"width": 100
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

		if not self.filters.show_delivered:
			columns = [c for c in columns if c['fieldname'] != 'status']

		if len(self.group_by) > 1:
			if "packing_slip" in self.group_by:
				columns = [c for c in columns if c['fieldname'] not in ('packing_slip', 'fabric_item', 'design_item')]

			if self.filters.totals_only:
				columns = [c for c in columns if c['fieldname'] not in ('design_item', 'design_item_name', 'sales_order', 'work_order')]

			reference_column = {
				"label": _("Reference"),
				"fieldname": "reference",
				"fieldtype": "Dynamic Link",
				"options": "reference_type",
				"width": 200
			}

			columns.insert(0, reference_column)

		self.columns = columns
