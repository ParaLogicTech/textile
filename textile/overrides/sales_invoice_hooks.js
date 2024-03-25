frappe.provide("textile");

frappe.ui.form.on("Sales Invoice", {
	setup: function (frm) {
		if (frm.fields_dict.printed_fabrics?.grid) {
			frm.fields_dict.printed_fabrics.grid.cannot_add_rows = 1;
		}
	},

	refresh: function (frm) {
		frm.add_custom_button(__('Check Printing Rate'), () => textile.print_pricing_dialog(), __("Prices"));
		frm.add_custom_button(__('Check Pretreatment Rate'), () => textile.pretreatment_pricing_dialog(), __("Prices"));
		frm.add_custom_button(__('Pretreatment Order'), function() {
			textile.get_items_from_pretreatment_order(
				frm,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_sales_invoice",
				null,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.get_pretreatment_orders_to_be_billed"
			);
		}, __("Get Items From"));
	},
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

	before_printed_fabrics_remove: function(frm, cdt, cdn) {
		var printed_fabrics_rows_selected = frm.get_selected().printed_fabrics
		var printed_fabrics_removed = [];
		for (let i in printed_fabrics_rows_selected) {
			printed_fabrics_removed.push.apply(printed_fabrics_removed, (frm.doc.printed_fabrics).filter(d => d.name === printed_fabrics_rows_selected[i]))
		}
		
		var parent_field = frm.get_field('items');
		for (let i in printed_fabrics_removed) {
			if (parent_field) {
				var rows = (frm.doc.items || []).filter(d => d.fabric_item === printed_fabrics_removed[i].fabric_item);
				$.each(rows, function (i, row) {
					let grid_row = parent_field.grid.grid_rows_by_docname[row.name];
					if (grid_row) {
						grid_row.remove();
					}
				});
			}	
		}
	}
});