// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.provide("textile");

textile.group_field_opts_preatpr = [
	"",
	"Group by Customer",
	"Group by Greige Fabric",
	"Group by Workstation",
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
			fieldname: "based_on",
			label: __("Based On"),
			fieldtype: "Select",
			options: ["Operation Entry", "Manufacture Entry"],
			default: "Operation Entry",
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
			fieldname: "ready_fabric",
			label: __("Ready Fabric"),
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
			fieldname: "customer_provided_items",
			label: __("Customer Provided Fabrics"),
			fieldtype: "Select",
			options: [
				"",
				"Customer Provided Items Only",
				"Exclude Customer Provided Items",
			]
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "pretreatment_order",
			label: __("Pretreatment Order"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				let filters = {
					company: frappe.query_report.get_filter_value("company")
				}
				let customer = frappe.query_report.get_filter_value("customer");
				if (customer) {
					filters.customer = customer;
				}
				return frappe.db.get_link_options('Pretreatment Order', txt, filters);
			}
		},
		{
			fieldname: "operation",
			label: __("Operation"),
			fieldtype: "Link",
			options: "Operation",
		},
		{
			fieldname: "singeing_item",
			label: __("Singeing Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Process Component",
						'process_component': "Singeing",
					}
				};
			},
		},
		{
			fieldname: "desizing_item",
			label: __("Desizing Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Process Component",
						'process_component': "Desizing",
					}
				};
			},
		},
		{
			fieldname: "bleaching_item",
			label: __("Bleaching Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Process Component",
						'process_component': "Bleaching",
					}
				};
			},
		},
		{
			fieldname: "group_by_1",
			label: __("Group By Level 1"),
			fieldtype: "Select",
			options: textile.group_field_opts_preatpr,
			default: "Group by Greige Fabric"
		},
		{
			fieldname: "group_by_2",
			label: __("Group By Level 2"),
			fieldtype: "Select",
			options: textile.group_field_opts_preatpr,
			default: ""
		},
		{
			fieldname: "totals_only",
			label: __("Group Totals Only"),
			fieldtype: "Check",
		},
	],
	initial_depth: 1,
};
