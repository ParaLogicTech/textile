frappe.provide("digital_printing");

frappe.ui.form.on("Packing Slip", {
	setup: function(frm) {
		frm.cscript.calculate_total_hooks.push(digital_printing.calculate_panel_qty);
	},
});

frappe.ui.form.on("Packing Slip Item", {
	panel_qty: function(frm, cdt, cdn) {
		digital_printing.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_totals();
	},
});
