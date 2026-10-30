# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, flt, add_days
from erpnext.manufacturing.report.production_register.production_register import ProductionRegister
from erpnext.setup.doctype.uom_conversion_factor.uom_conversion_factor import get_uom_conv_factor


def execute(filters=None):
	return PrintProductionRegister(filters).run()


class PrintProductionRegister(ProductionRegister):
	def validate_filters(self):
		super().validate_filters()
		self.filters.based_on = "Manufacture Entry"

	def set_fieldnames(self):
		super().set_fieldnames()
		self.qty_fields += ["length", "area", "net_weight"]

	def get_select_fields_and_joins(self):
		select_fields, joins = super().get_select_fields_and_joins()

		select_fields += [
			"wo.print_order",
			"wo.production_item as design_item",
			"wo.item_name as design_item_name",
			"wo.fabric_item",
			"wo.fabric_item_name",
			"wo.process_item",
			"wo.process_item_name",
			"pro.softener_item",
			"pro.softener_item_name",
			"im.net_weight_per_unit",
			"im.weight_uom",
			"ste.fabric_printer",
		]

		joins.append("inner join `tabPrint Order` pro on pro.name = wo.print_order")

		joins.remove("left join `tabItem` im ON im.name = wo.production_item")
		joins.append("left join `tabItem` im ON im.name = wo.fabric_item")

		return select_fields, joins

	def get_data(self):
		super().get_data()

		self.fabric_items = list(set([d.fabric_item for d in self.data]))
		self.square_meter_conversion = {}

		if self.fabric_items:
			self.square_meter_conversion = dict(frappe.db.sql("""
				select parent, conversion_factor
				from `tabUOM Conversion Detail`
				where parenttype = 'Item' and parent in %s and uom = 'Square Meter'
			""", [self.fabric_items]))

	def get_conditions(self):
		conditions = super().get_conditions()

		if self.filters.fabric_item:
			conditions.append("wo.fabric_item = %(fabric_item)s")

		if self.filters.fabric_material:
			conditions.append("im.fabric_material = %(fabric_material)s")

		if self.filters.fabric_type:
			conditions.append("im.fabric_type = %(fabric_type)s")

		if self.filters.process_item:
			conditions.append("wo.process_item = %(process_item)s")

		if self.filters.softener_item:
			conditions.append("pro.softener_item = %(softener_item)s")

		if self.filters.fabric_printer:
			conditions.append("ste.fabric_printer = %(fabric_printer)s")

		if self.filters.print_order:
			if isinstance(self.filters.print_order, str):
				self.filters.print_order = cstr(self.filters.print_order).strip()
				self.filters.print_order = [d.strip() for d in self.filters.print_order.split(',') if d]

			conditions.append("wo.print_order in %(print_order)s")

		return conditions

	def prepare_data(self):
		super().prepare_data()
		for d in self.data:
			d.length = d.qty * get_uom_conv_factor(d.uom, "Meter")

			if self.square_meter_conversion.get(d.fabric_item):
				d.area = flt(d.qty) * flt(self.square_meter_conversion.get(d.fabric_item))

			if d.net_weight_per_unit:
				d.net_weight = flt(d.net_weight_per_unit) * flt(d.qty) * get_uom_conv_factor(d.weight_uom, "Kg")

	def calculate_group_totals(self, data, group_field, group_value, grouped_by):
		totals = super().calculate_group_totals(data, group_field, group_value, grouped_by)

		if totals.get("print_order") and data:
			totals.customer = data[0].get("customer")
			totals.process_item = data[0].get("process_item")
			totals.fabric_item = data[0].get("fabric_item")
			totals.softener_item = data[0].get("softener_item")

		if totals.get("fabric_item"):
			totals["fabric_item_name"] = data[0].fabric_item_name

		if totals.get("process_item"):
			totals["process_item_name"] = data[0].process_item_name

		if totals.get("softener_item"):
			totals["softener_item_name"] = data[0].softener_item_name

		if totals.get("customer"):
			totals["customer_name"] = data[0].customer_name

		return totals

	def fieldname_to_doctype(self, fieldname):
		if fieldname in ("fabric_item", "process_item", "softener_item", "design_item"):
			return "Item"

		return super().fieldname_to_doctype(fieldname)

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
				"label": _("Process"),
				"fieldname": "process_item_name",
				"fieldtype": "Data",
				"width": 100
			},
			{
				"label": _("Printer"),
				"fieldname": "fabric_printer",
				"fieldtype": "Link",
				"options": "Fabric Printer",
				"width": 80
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
			{
				"label": _("Softener Item"),
				"fieldname": "softener_item",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100 if self.show_item_name else 150
			},
			{
				"label": _("Softener Name"),
				"fieldname": "softener_item_name",
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
					'posting_dt', 'print_order',
					'work_order', 'stock_entry', 'fabric_printer',
					'design_item', 'design_item_name',
					'fabric_item', 'fabric_item_name',
					'process_item', 'process_item_name',
					'softener_item', 'softener_item_name',
					'customer', 'customer_name',
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
					exclude_columns.remove('process_item')
					exclude_columns.remove('process_item_name')

				if "fabric_printer" in self.group_by:
					exclude_columns.remove('fabric_printer')

		if not self.show_customer_name:
			exclude_columns.add('customer_name')

		if not self.show_item_name:
			exclude_columns.add('fabric_item_name')
			exclude_columns.add('design_item_name')
			exclude_columns.add('softener_item_name')
			exclude_columns.add('process_item_name')

		columns = [c for c in columns if c['fieldname'] not in exclude_columns]

		self.columns = columns
