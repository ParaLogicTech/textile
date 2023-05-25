frappe.provide("digital_printing");

frappe.ui.form.on("Sales Invoice Item", {
	panel_qty: function(frm, cdt, cdn) {
		digital_printing.calculate_panel_length_meter(frm, cdt, cdn);
	}
});
