// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */

let group_field_opts = [
	"",
	"Group by Customer",
	"Group by Customer Group",
	"Group by Fabric Item",
	"Group by Item",
	"Group by Item Group",
	"Group by Brand",
	"Group by Territory",
	"Group by Sales Person",
	"Group by Transaction",
]


frappe.query_reports["Fabric Delivery Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			bold: 1
		},
		{
			fieldname: "qty_field",
			label: __("Quantity Type"),
			fieldtype: "Select",
			options: ["Stock Qty", "Contents Qty", "Transaction Qty"],
			default: "Stock Qty",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.customer_query"
				};
			}
		},
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group"
		},
		{
			fieldname: "fabric_item",
			label: __("Fabric Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Ready Fabric"
					}
				};
			},
			on_change: () => {
				var item = frappe.query_report.get_filter_value('fabric_item');
				if (item) {
					frappe.db.get_value('Item', item, ["item_name"], function(value) {
						frappe.query_report.set_filter_value('fabric_item_name', value["item_name"]);
					});
				} else {
					frappe.query_report.set_filter_value('fabric_item_name', "");
				}
			},
		},
		{
			fieldname: "fabric_item_name",
			label: __("Fabric Item Name"),
			fieldtype: "Data",
			read_only: 1,
			hidden: 1,
		},
		{
			fieldname: "fabric_material",
			label: __("Fabric Material"),
			fieldtype: "Link",
			options: "Fabric Material",
		},
		{
			fieldname: "fabric_type",
			label: __("Fabric Type"),
			fieldtype: "Link",
			options: "Fabric Type",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {'include_disabled': 1,'include_templates':1}
				}
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group"
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand"
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: function() {
				return {
					filters: {'company': frappe.query_report.get_filter_value("company")}
				}
			},
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory"
		},
		{
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Person"
		},
		{
			fieldname: "group_by_1",
			label: __("Group By Level 1"),
			fieldtype: "Select",
			options: group_field_opts,
			default: ""
		},
		{
			fieldname: "group_by_2",
			label: __("Group By Level 2"),
			fieldtype: "Select",
			options: group_field_opts,
			default: "Group by Fabric Item"
		},
		{
			fieldname: "totals_only",
			label: __("Group Totals Only"),
			fieldtype: "Check",
		},
		{
			fieldname: "group_same_items",
			label: __("Group Same Items"),
			fieldtype: "Check",
		},
	],
	formatter: function(value, row, column, data, default_formatter) {
		let style = {};

		if (data && data.is_return_fabric) {
			style['color'] = 'var(--alert-text-info)';
		}

		if (['qty'].includes(column.fieldname)) {
			if (flt(value) < 0) {
				style['color'] = 'var(--red-500)';
			}
		}

		return default_formatter(value, row, column, data, {css: style});
	},
	"initial_depth": 1
};
