// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fabric Pretreatment Settings', {
	onload: function(frm) {
		erpnext.queries.setup_queries(frm, "Warehouse", function(fieldname) {
			return erpnext.queries.warehouse(frm.doc);
		});
	}
});
