// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fabric Printing Settings', {
	onload: function(frm) {
		erpnext.queries.setup_queries(frm, "Warehouse", function(fieldname) {
			return erpnext.queries.warehouse(frm.doc);
		});

		frm.set_query("stock_entry_type_for_fabric_transfer", function(doc) {
			return {
				filters: {
					purpose: "Material Transfer for Manufacture",
				}
			};
		});
		frm.set_query("stock_entry_type_for_print_production", function(doc) {
			return {
				filters: {
					purpose: "Manufacture",
				}
			};
		});
		frm.set_query("stock_entry_type_for_fabric_coating", function(doc) {
			return {
				filters: {
					purpose: "Manufacture",
				}
			};
		});
		frm.set_query("stock_entry_type_for_fabric_shrinkage", function(doc) {
			return {
				filters: {
					purpose: "Material Issue",
				}
			};
		});
		frm.set_query("stock_entry_type_for_fabric_rejection", function(doc) {
			return {
				filters: {
					purpose: "Material Transfer",
				}
			};
		});
	}
});
