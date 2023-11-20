// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */


let group_field_opts = [
	"",
	"Group by Customer",
	"Group by Greige Fabric",
	"Group by Pretreatment Order",
];

frappe.query_reports["Pretreatment Production Register"] = {
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
			fieldname: "greige_fabric",
			label: __("Greige Fabric"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Greige Fabric"
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
			"fieldname":"pretreatment_order",
			"label": __("Pretreatment Order"),
			"fieldtype": "MultiSelectList",
			get_data: function(txt) {
				let filters = {
					company: frappe.query_report.get_filter_value("company")
				}
				customer = frappe.query_report.get_filter_value("customer");
				if (customer) {
					filters.customer = customer;
				}
				return frappe.db.get_link_options('Pretreatment Order', txt, filters);
			}
		},
		{
			fieldname: "group_by_1",
			label: __("Group By Level 1"),
			fieldtype: "Select",
			options: group_field_opts,
			default: "Group by Customer"
		},
		{
			fieldname: "group_by_2",
			label: __("Group By Level 2"),
			fieldtype: "Select",
			options: group_field_opts,
			default: "Group by Greige Fabric"
		},
		{
			fieldname: "group_by_3",
			label: __("Group By Level 3"),
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
	initial_depth: 2
};
