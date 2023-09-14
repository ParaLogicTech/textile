# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

# import frappe
from frappe import _
from erpnext.selling.report.sales_details.sales_details import SalesPurchaseDetailsReport


def execute(filters=None):
	updated_filters = {
		"qty_only": 1,
		"show_packing_slip": 1,
	}
	updated_filters.update(filters or {})

	return FabricSalesPurchaseReport(updated_filters, doctype="Delivery Note").run()


class FabricSalesPurchaseReport(SalesPurchaseDetailsReport):
	def set_fieldnames(self):
		super().set_fieldnames()
		self.qty_fields += ["return_qty", "total_qty", "panel_qty"]

	def get_select_fields_and_joins(self):
		select_fields, joins = super().get_select_fields_and_joins()

		joins.append("left join `tabItem` fabric on fabric.name = im.fabric_item")

		select_fields += [
			"im.fabric_item",
			"fabric.item_name as fabric_item_name",
			"im.textile_item_type",
			"i.print_order",
			"i.pretreatment_order",
			"i.is_return_fabric",
			"i.panel_qty",
		]

		return select_fields, joins

	def get_conditions(self):
		conditions = super().get_conditions()

		if self.filters.fabric_item:
			conditions.append("(im.fabric_item = %(fabric_item)s or (im.item_code = %(fabric_item)s))")

		if self.filters.fabric_material:
			conditions.append("im.fabric_material = %(fabric_material)s")

		if self.filters.fabric_type:
			conditions.append("im.fabric_type = %(fabric_type)s")

		return conditions

	def prepare_data(self):
		super().prepare_data()

		for d in self.entries:
			if not d.panel_qty:
				d.panel_qty = None

			d.total_qty = d.qty
			if d.is_return_fabric:
				d.return_qty = d.qty
				d.qty = None

			if d.textile_item_type in ("Ready Fabric", "Greige Fabric"):
				d.fabric_item = d.item_code
				d.fabric_item_name = d.item_name

	def calculate_group_totals(self, data, group_field, group_value, grouped_by):
		totals = super().calculate_group_totals(data, group_field, group_value, grouped_by)

		fabric_items = set([d.fabric_item for d in data if d.fabric_item])
		if len(fabric_items) == 1:
			totals['fabric_item'] = list(fabric_items)[0]

		if totals.get('fabric_item'):
			totals['fabric_item_name'] = data[0].fabric_item_name

		if totals.get("parent"):
			pretreatment_orders = set([d.pretreatment_order for d in data if d.pretreatment_order])
			if len(pretreatment_orders) == 1:
				totals.pretreatment_order = list(pretreatment_orders)[0]

			print_orders = set([d.print_order for d in data if d.print_order])
			if len(print_orders) == 1:
				totals.print_order = list(print_orders)[0]

		return totals

	def fieldname_to_doctype(self, fieldname):
		if fieldname == "fabric_item":
			return "Item"
		
		return super().fieldname_to_doctype(fieldname)

	def get_columns(self):
		columns = super().get_columns()

		item_code_index = next(i for i, c in enumerate(columns) if c.get("fieldname") == "item_code")
		columns.insert(item_code_index, {
			"label": _("Fabric Name"),
			"fieldname": "fabric_item_name",
			"fieldtype": "Data",
			"width": 150
		})

		qty_index = next(i for i, c in enumerate(columns) if c.get("fieldname") == "qty")
		columns[qty_index+1:qty_index+1] = [
			{
				"label": _("Return Qty"),
				"fieldname": "return_qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Total Qty"),
				"fieldname": "total_qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Panels"),
				"fieldname": "panel_qty",
				"fieldtype": "Float",
				"precision": 1,
				"width": 70
			},
		]

		packing_slip_index = next(i for i, c in enumerate(columns) if c.get("fieldname") == "packing_slip")
		columns[packing_slip_index + 1:packing_slip_index + 1] = [
			{
				"label": _("Print Order"),
				"fieldname": "print_order",
				"fieldtype": "Link",
				"options": "Print Order",
				"width": 100
			},
			{
				"label": _("Pretreatment Order"),
				"fieldname": "pretreatment_order",
				"fieldtype": "Link",
				"options": "Pretreatment Order",
				"width": 100
			},
		]

		return columns
