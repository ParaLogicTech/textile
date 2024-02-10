frappe.provide("textile");

frappe.ui.form.on("Sales Invoice", {
	setup: function (frm) {
		if (frm.fields_dict.printed_fabrics?.grid) {
			frm.fields_dict.printed_fabrics.grid.cannot_add_rows = 1;
		}
	},

	refresh: function (frm) {
		frm.add_custom_button(__('Pretreatment Order'), function() {
			textile.get_items_from_pretreatment_order(
				frm,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_sales_invoice",
				null,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.get_pretreatment_orders_to_be_billed"
			);
		}, __("Get Items From"));
	}
});

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
