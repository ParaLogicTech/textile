// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fabric Printer', {
	setup: function(frm) {
		frm.set_query("process_item", "process_items", () => {
			return erpnext.queries.item({ textile_item_type: 'Print Process' });
		});
	}
});
