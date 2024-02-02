frappe.provide("textile");

frappe.ui.form.on("Sales Invoice Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_taxes_and_totals();
	},
});

frappe.ui.form.on("Printed Fabric Detail", {
	fabric_rate: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		textile.set_printed_fabric_rate(frm, row);
		frm.cscript.calculate_taxes_and_totals();
	},
});
