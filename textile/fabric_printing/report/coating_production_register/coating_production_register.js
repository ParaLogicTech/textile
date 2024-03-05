// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */


let group_field_opts = [
	"",
	"Group by Customer",
	"Group by Fabric Item",
	"Group by Coating Order",
];

frappe.query_reports["Coating Production Register"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			"fieldname":"coating_order",
			"label": __("Coating Order"),
			"fieldtype": "MultiSelectList",
			get_data: function(txt) {
				let filters = {
					company: frappe.query_report.get_filter_value("company")
				}
				customer = frappe.query_report.get_filter_value("customer");
				if (customer) {
					filters.customer = customer;
				}
				return frappe.db.get_link_options('Coating Order', txt, filters);
			}
		},
		{
			fieldname: "group_by_1",
			label: __("Group By Level 1"),
			fieldtype: "Select",
			options: group_field_opts,
			default: "Group by Fabric Item"
		},
		{
			fieldname: "group_by_2",
			label: __("Group By Level 2"),
			fieldtype: "Select",
			options: group_field_opts,
			default: ""
		},
		{
			fieldname: "totals_only",
			label: __("Group Totals Only"),
			fieldtype: "Check",
		},
	],
	initial_depth: 1
};
