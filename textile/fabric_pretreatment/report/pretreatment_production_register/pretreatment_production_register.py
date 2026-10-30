# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, flt
from erpnext.manufacturing.report.production_register.production_register import ProductionRegister
from erpnext.setup.doctype.uom_conversion_factor.uom_conversion_factor import get_uom_conv_factor


def execute(filters=None):
	return PretreatmentProductionRegister(filters).run()


class PretreatmentProductionRegister(ProductionRegister):
	def set_fieldnames(self):
		super().set_fieldnames()
		self.qty_fields += ["length", "area", "net_weight"]

	def get_select_fields_and_joins(self):
		select_fields, joins = super().get_select_fields_and_joins()

		select_fields += [
			"wo.pretreatment_order",
			"wo.production_item as ready_fabric",
			"wo.item_name as ready_fabric_name",
			"wo.fabric_item as greige_fabric",
			"wo.fabric_item_name as greige_fabric_name",
			"im.net_weight_per_unit",
			"im.weight_uom",
		]

		joins.append("inner join `tabPretreatment Order` pro on pro.name = wo.pretreatment_order")

		joins.remove("left join `tabItem` im ON im.name = wo.production_item")
		joins.append("left join `tabItem` im ON im.name = wo.fabric_item")

		return select_fields, joins

	def get_data(self):
		super().get_data()

		greige_fabrics = list(set([d.greige_fabric for d in self.data]))
		self.square_meter_conversion = {}
		if greige_fabrics:
			self.square_meter_conversion = dict(frappe.db.sql("""
				select parent, conversion_factor
				from `tabUOM Conversion Detail`
				where parenttype = 'Item' and parent in %s and uom = 'Square Meter'
			""", [greige_fabrics]))

	def get_conditions(self):
		conditions = super().get_conditions()

		if self.filters.greige_fabric:
			conditions.append("wo.fabric_item = %(greige_fabric)s")

		if self.filters.ready_fabric:
			conditions.append("wo.production_item = %(ready_fabric)s")

		if self.filters.fabric_material:
			conditions.append("im.fabric_material = %(fabric_material)s")

		if self.filters.fabric_type:
			conditions.append("im.fabric_type = %(fabric_type)s")

		if self.filters.singeing_item:
			conditions.append("pro.singeing_item = %(singeing_item)s")

		if self.filters.desizing_item:
			conditions.append("pro.desizing_item = %(desizing_item)s")

		if self.filters.bleaching_item:
			conditions.append("pro.bleaching_item = %(bleaching_item)s")

		if self.filters.pretreatment_order:
			if isinstance(self.filters.pretreatment_order, str):
				self.filters.pretreatment_order = cstr(self.filters.pretreatment_order).strip()
				self.filters.pretreatment_order = [d.strip() for d in self.filters.pretreatment_order.split(',') if d]

			conditions.append("wo.pretreatment_order in %(pretreatment_order)s")

		return conditions

	def prepare_data(self):
		super().prepare_data()
		for d in self.data:
			d.length = d.qty * get_uom_conv_factor(d.uom, "Meter")

			if self.square_meter_conversion.get(d.greige_fabric):
				d.area = flt(d.qty) * flt(self.square_meter_conversion.get(d.greige_fabric))

			if d.net_weight_per_unit:
				d.net_weight = flt(d.net_weight_per_unit) * flt(d.qty) * get_uom_conv_factor(d.weight_uom, "Kg")

	def calculate_group_totals(self, data, group_field, group_value, grouped_by):
		totals = super().calculate_group_totals(data, group_field, group_value, grouped_by)

		if totals.get("pretreatment_order") and data:
			totals.customer = data[0].get("customer")
			totals.greige_fabric = data[0].get("greige_fabric")
			totals.ready_fabric = data[0].get("ready_fabric")

		if totals.get("greige_fabric") and data:
			totals["greige_fabric_name"] = data[0].greige_fabric_name

		if totals.get("ready_fabric") and data:
			totals["ready_fabric_name"] = data[0].ready_fabric_name

		if totals.get("customer"):
			totals["customer_name"] = data[0].customer_name

		return totals

	def fieldname_to_doctype(self, fieldname):
		if fieldname == "greige_fabric":
			return "Item"

		return super().fieldname_to_doctype(fieldname)

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
				"label": _("Operation"),
				"fieldname": "operation",
				"fieldtype": "Link",
				"options": "Operation",
				"width": 90
			},
			{
				"label": _("Workstation"),
				"fieldname": "workstation",
				"fieldtype": "Link",
				"options": "Workstation",
				"width": 90
			},
			{
				"label": _("Pretreatment Order"),
				"fieldname": "pretreatment_order",
				"fieldtype": "Link",
				"options": "Pretreatment Order",
				"width": 110
			},
			{
				"label": _("Work Order"),
				"fieldname": "work_order",
				"fieldtype": "Link",
				"options": "Work Order",
				"width": 100
			},
			{
				"label": _("Job Card"),
				"fieldname": "job_card",
				"fieldtype": "Link",
				"options": "Job Card",
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
				"label": _("Greige Fabric"),
				"fieldname": "greige_fabric",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100 if self.show_item_name else 150
			},
			{
				"label": _("Greige Fabric Name"),
				"fieldname": "greige_fabric_name",
				"fieldtype": "Data",
				"width": 160
			},
			{
				"label": _("Ready Fabric"),
				"fieldname": "ready_fabric",
				"fieldtype": "Link",
				"options": "Item",
				"width": 100 if self.show_item_name else 150
			},
			{
				"label": _("Ready Fabric Name"),
				"fieldname": "ready_fabric_name",
				"fieldtype": "Data",
				"width": 160
			},
		]

		exclude_columns = set()

		if self.filters.based_on != "Operation Entry":
			exclude_columns.add("operation")
			exclude_columns.add("workstation")
			exclude_columns.add("job_card")

		if len(self.group_by) > 1:
			columns.insert(0, {
				"label": _("Reference"),
				"fieldname": "reference",
				"fieldtype": "Dynamic Link",
				"options": "reference_type",
				"width": 200
			})

			if self.filters.based_on == "Operation Entry":
				exclude_columns.add("job_card")
			else:
				exclude_columns.add("stock_entry")

			if self.filters.totals_only:
				# potential empty columns
				exclude_columns = exclude_columns.union({
					'posting_dt', 'pretreatment_order',
					'work_order', 'stock_entry',
					'job_card', 'workstation',
					'customer', 'customer_name',
					'greige_fabric', 'greige_fabric_name',
					'ready_fabric', 'ready_fabric_name',
				})

				if "customer" in self.group_by:
					exclude_columns.remove('customer')
					exclude_columns.remove('customer_name')

				if "greige_fabric" in self.group_by:
					exclude_columns.remove('greige_fabric')
					exclude_columns.remove('greige_fabric_name')

				if "workstation" in self.group_by:
					exclude_columns.remove('workstation')

				if "pretreatment_order" in self.group_by:
					exclude_columns.remove('pretreatment_order')

		if not self.show_customer_name:
			exclude_columns.add('customer_name')

		if not self.show_item_name:
			exclude_columns.add('greige_fabric_name')
			exclude_columns.add('ready_fabric_name')

		columns = [c for c in columns if c['fieldname'] not in exclude_columns]

		self.columns = columns
