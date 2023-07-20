frappe.ui.form.on('Item', {
	setup: function(frm) {
		frm.events.setup_custom_queries(frm);
	},

	setup_custom_queries(frm) {
		frm.set_query("fabric_item", function() {
			return {
				filters: { 'textile_item_type': 'Ready Fabric' }
			}
		});
	},

	textile_item_type(frm) {
		if (frm.doc.textile_item_type != "Printed Design" && frm.doc.fabric_item) {
			frm.set_value("fabric_item", null)
		}
	}
});
