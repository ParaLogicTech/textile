frappe.provide("textile");

frappe.ui.form.on("Purchase Order", {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Pretreatment Order'), function() {
				textile.get_items_from_pretreatment_order(
					frm,
					"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_purchase_order",
					{production_status: "To Produce", subcontractable_qty: [">", 0]}
				);
			}, __("Get Items From"));
		}
	},
});
