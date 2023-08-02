// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Print Production"] = {
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
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
			"fieldname":"print_order",
			"label": __("Print Order"),
			"fieldtype": "MultiSelectList",
			get_data: function(txt) {
				let filters = {
					company: frappe.query_report.get_filter_value("company")
				}
				customer = frappe.query_report.get_filter_value("customer");
				if (customer) {
					filters.customer = customer;
				}
				return frappe.db.get_link_options('Print Order', txt, filters);
			}
		},
		{
			fieldname: "print_process",
			label: __("Print Process"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {
						'textile_item_type': "Print Process"
					}
				};
			},
		},
		{
			"fieldname":"fabric_printer",
			"label": __("Fabric Printer"),
			"fieldtype": "Link",
			"options": "Fabric Printer",
			get_query: function() {
				let print_process = frappe.query_report.get_filter_value("print_process");
				let filters = print_process ? {process_item: print_process} : {}
				return {
					filters: filters
				}
			},
		},
	]
};
