frappe.provide("textile");

frappe.ui.form.on("Sales Order", {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Print Order'), function() {
				textile.get_items_from_print_order(
					frm,
					"textile.digital_printing.doctype.print_order.print_order.make_sales_order",
					{per_ordered: ["<", 100]}
				);
			}, __("Get Items From"));
		}
	},
});

frappe.ui.form.on("Sales Order Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_taxes_and_totals();
	},
});
