// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fabric Material', {
	// refresh: function(frm) {

	// }

	setup: function(frm) {
		frm.set_query("default_process_item", () => {
			return erpnext.queries.item({ print_item_type: 'Print Process' });
		});
	}
});
