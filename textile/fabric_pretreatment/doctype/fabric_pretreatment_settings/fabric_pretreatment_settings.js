// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fabric Pretreatment Settings', {
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
		frm.set_query("stock_entry_type_for_pretreatment_production", function(doc) {
			return {
				filters: {
					purpose: "Manufacture",
				}
			};
		});
		frm.set_query("stock_entry_type_for_operation_consumption", function(doc) {
			return {
				filters: {
					purpose: "Material Consumption for Manufacture",
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
