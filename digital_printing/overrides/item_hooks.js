frappe.ui.form.on('Item', {
	setup: function(frm) {
		frm.events.setup_custom_queries(frm);

	},

	setup_custom_queries(frm) {
		frm.set_query("process_item", function() {
			return {
				filters: { 'print_item_type': 'Print Process' }
			}
		});
		frm.set_query("fabric_item", function() {
			return {
				filters: { 'print_item_type': 'Fabric' }
			}
		});

	},

	print_item_type(frm) {
		if (frm.doc.print_item_type != "Printed Design") {
			frm.set_value("fabric_item", null)
		}
	}
});
