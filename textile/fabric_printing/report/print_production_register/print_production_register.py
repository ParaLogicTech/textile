# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, unscrub
from frappe.utils import cint, cstr, flt, getdate, add_days
from frappe.desk.query_report import group_report_data
from erpnext.setup.doctype.uom_conversion_factor.uom_conversion_factor import get_uom_conv_factor


def execute(filters=None):
	return PrintProductionRegister(filters).run()


class PrintProductionRegister:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.from_date = getdate(filters.from_date)
		self.filters.to_date = getdate(filters.to_date)

		if self.filters.from_date > self.filters.to_date:
			frappe.throw(_("Date Range is incorrect"))

		self.show_item_name = frappe.defaults.get_global_default('item_naming_by') != "Item Name"
		self.show_customer_name = frappe.defaults.get_global_default('cust_master_name') == "Naming Series"

	def run(self):
		self.get_data()
		self.prepare_data()
		self.get_chart_data()
		self.data = self.get_grouped_data()
		self.get_columns()

		return self.columns, self.data, None, self.chart_data

	def get_data(self):
		conditions = self.get_conditions()

		self.data = frappe.db.sql("""
			SELECT se.name as stock_entry, se.posting_date, se.posting_time,
				timestamp(se.posting_date, se.posting_time) as posting_dt,
				se.work_order, se.fabric_printer, se.fg_completed_qty as qty,
				wo.print_order, wo.stock_uom as uom,
				wo.customer, wo.customer_name,
				wo.production_item as design_item, wo.item_name as design_item_name,
				wo.process_item, wo.process_item_name,
				wo.fabric_item, wo.fabric_item_name,
				item.net_weight_per_unit, item.weight_uom
			FROM `tabStock Entry` se
			INNER JOIN `tabWork Order` wo
				ON wo.name = se.work_order
			LEFT JOIN `tabItem` item
				ON item.name = wo.fabric_item
			WHERE se.docstatus = 1
				AND se.posting_date between %(from_date)s AND %(to_date)s
				AND se.purpose = 'Manufacture'
				AND ifnull(wo.print_order, '') != ''
				{conditions}
			ORDER BY se.posting_date, se.posting_time, se.fabric_printer
		""".format(conditions=conditions), self.filters, as_dict=1)

		self.design_items = list(set([d.design_item for d in self.data]))
		self.square_meter_conversion = {}

		if self.design_items:
			self.square_meter_conversion = dict(frappe.db.sql("""
				select parent, conversion_factor
				from `tabUOM Conversion Detail`
				where parenttype = 'Item' and parent in %s and uom = 'Square Meter'
			""", [self.design_items]))

	def get_conditions(self):
		conditions = []

		if self.filters.company:
			conditions.append("se.company = %(company)s")

		if self.filters.customer:
			conditions.append("wo.customer = %(customer)s")

		if self.filters.fabric_item:
			conditions.append("wo.fabric_item = %(fabric_item)s")

		if self.filters.fabric_material:
			conditions.append("item.fabric_material = %(fabric_material)s")

		if self.filters.fabric_type:
			conditions.append("item.fabric_type = %(fabric_type)s")

		if self.filters.print_order:
			if isinstance(self.filters.print_order, str):
				self.filters.print_order = cstr(self.filters.print_order).strip()
				self.filters.print_order = [d.strip() for d in self.filters.print_order.split(',') if d]

			conditions.append("wo.print_order in %(print_order)s")

		if self.filters.process_item:
			conditions.append("wo.process_item = %(process_item)s")

		if self.filters.fabric_printer:
			conditions.append("se.fabric_printer = %(fabric_printer)s")

		return "AND {}".format(" AND ".join(conditions)) if conditions else ""

	def prepare_data(self):
		for d in self.data:
			d.disable_item_formatter = 1

			d.reference_type = "Stock Entry"
			d.reference = d.stock_entry

			d.length = d.qty * get_uom_conv_factor(d.uom, "Meter")

			if self.square_meter_conversion.get(d.design_item):
				d.area = flt(d.qty) * flt(self.square_meter_conversion.get(d.design_item))

			if d.net_weight_per_unit:
				d.net_weight = flt(d.net_weight_per_unit) * flt(d.qty) * get_uom_conv_factor(d.weight_uom, "Kg")

	def get_grouped_data(self):
		data = self.data

		self.group_by = [None]
		for i in range(3):
			group_label = self.filters.get("group_by_" + str(i + 1), "").replace("Group by ", "")

			if group_label:
				self.group_by.append(scrub(group_label))

		if len(self.group_by) <= 1:
			return data

		return group_report_data(data, self.group_by, calculate_totals=self.calculate_group_totals,
			totals_only=self.filters.totals_only)

	def calculate_group_totals(self, data, group_field, group_value, grouped_by):
		totals = frappe._dict()

		# Copy grouped by into total row
		for f, g in grouped_by.items():
			totals[f] = g

		# Sum
		uoms = set()
		sum_fields = ['length', 'area', 'net_weight']
		for d in data:
			for f in sum_fields:
				totals[f] = flt(totals.get(f)) + flt(d.get(f))

			uoms.add(d.uom)

		if len(uoms) == 1:
			totals.uom = list(uoms)[0]

		group_reference_doctypes = {
			"process_item": "Item",
			"fabric_item": "Item",
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

		if totals.get('fabric_item'):
			totals['fabric_item_name'] = data[0].fabric_item_name

		if totals.get('process_item'):
			totals['process_item_name'] = data[0].process_item_name

		if totals.get('customer'):
			totals['customer_name'] = data[0].customer_name

		return totals

	def get_chart_data(self):
		dates = []
		current_date = self.filters.from_date
		while current_date <= self.filters.to_date:
			dates.append(current_date)
			current_date = add_days(current_date, 1)

		grand_totals = {}
		process_totals = {}

		for d in self.data:
			grand_totals.setdefault(d.posting_date, 0)
			grand_totals[d.posting_date] += d.length

			process_totals.setdefault(d.process_item, {}).setdefault(d.posting_date, 0)
			process_totals[d.process_item][d.posting_date] += d.length

		labels = [frappe.format(d) for d in dates]

		total_dataset = {"name": _("Total Production"), "values": []}
		for current_date in dates:
			total_dataset["values"].append(flt(grand_totals.get(current_date)))

		process_datasets = {}
		for process_item, process_total_dict in process_totals.items():
			process_datasets.setdefault(process_item, {
				"name": frappe.get_cached_value("Item", process_item, "item_name"), "values": []
			})
			for current_date in dates:
				process_datasets[process_item]["values"].append(flt(process_total_dict.get(current_date)))

		self.chart_data = {
			"data": {
				"labels": labels,
				'datasets': [total_dataset] + list(process_datasets.values())
			},
			"colors": ['purple', 'light-blue', 'light-pink'],
			"type": "line",
			"fieldtype": "Float",
		}

		return self.chart_data

	def get_columns(self):
		columns = [
			{
				"label": _("Date/Time"),
				"fieldname": "posting_dt",
				"fieldtype": "Datetime",
				"width": 90
			},
			{
				"label": _("Printer"),
				"fieldname": "fabric_printer",
				"fieldtype": "Link",
				"options": "Fabric Printer",
				"width": 80
			},
			{
				"label": _("Process"),
				"fieldname": "process_item_name",
				"fieldtype": "Data",
				"width": 100
			},
			{
				"label": _("Length (Meter)"),
				"fieldname": "length",
				"fieldtype": "Float",
				"width": 100
			},
			{
				"label": _("Area (Sq. Mtr)"),
				"fieldname": "area",
				"fieldtype": "Float",
				"width": 100
			},
			{
				"label": _("Weight (Kg)"),
				"fieldname": "net_weight",
				"fieldtype": "Float",
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
				"label": _("Work Order"),
				"fieldname": "work_order",
				"fieldtype": "Link",
				"options": "Work Order",
				"width": 100
			},
			{
				"label": _("Stock Entry"),
				"fieldname": "stock_entry",
				"fieldtype": "Link",
				"options": "Stock Entry",
				"width": 120
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
				"width": 160
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
				"width": 160
			},
		]

		exclude_columns = set()

		if len(self.group_by) > 1:
			columns.insert(0, {
				"label": _("Reference"),
				"fieldname": "reference",
				"fieldtype": "Dynamic Link",
				"options": "reference_type",
				"width": 200
			})

			exclude_columns.add('stock_entry')

			if self.filters.totals_only:
				# potential empty columns
				exclude_columns = exclude_columns.union({
					'posting_dt', 'work_order', 'design_item', 'design_item_name', 'customer', 'customer_name',
					'fabric_item', 'fabric_item_name', 'print_order', 'process_item_name', 'fabric_printer'
				})

				if "customer" in self.group_by:
					exclude_columns.remove('customer')
					exclude_columns.remove('customer_name')

				if "fabric_item" in self.group_by:
					exclude_columns.remove('fabric_item')
					exclude_columns.remove('fabric_item_name')

				if "print_order" in self.group_by:
					exclude_columns.remove('print_order')

				if "process_item" in self.group_by:
					exclude_columns.remove('process_item_name')

				if "fabric_printer" in self.group_by:
					exclude_columns.remove('fabric_printer')

		if not self.show_customer_name:
			exclude_columns.add('customer_name')

		if not self.show_item_name:
			exclude_columns.add('fabric_item_name')
			exclude_columns.add('design_item_name')

		columns = [c for c in columns if c['fieldname'] not in exclude_columns]

		self.columns = columns
