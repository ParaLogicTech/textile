frappe.provide("textile");

frappe.ui.form.on("Packing Slip", {
	setup: function(frm) {
		frm.cscript.calculate_total_hooks.push(textile.calculate_panel_qty);
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
