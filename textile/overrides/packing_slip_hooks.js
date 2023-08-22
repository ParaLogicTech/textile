frappe.provide("textile");

frappe.ui.form.on("Packing Slip", {
	setup: function(frm) {
		frm.cscript.calculate_total_hooks.push(textile.calculate_panel_qty);
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Print Order'), function() {
				textile.get_items_from_print_order(
					frm,
					"textile.fabric_printing.doctype.print_order.print_order.make_packing_slip",
					{packing_status: "To Pack"}
				);
			}, __("Get Items From"));
		}
	},
});

frappe.ui.form.on("Packing Slip Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_totals();
	},
});
