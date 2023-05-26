frappe.provide("textile");

textile.calculate_panel_qty = function() {
	if (
		!frappe.meta.has_field(this.frm.doc.doctype + " Item", 'panel_length_meter')
		|| !frappe.meta.has_field(this.frm.doc.doctype + " Item", 'panel_qty')
	) {
		return;
	}

	for (let row of this.frm.doc.items || []) {
		if (cint(row.panel_based_qty) && flt(row.panel_length_meter)) {
			row.panel_qty = flt(flt(row.stock_qty) / flt(row.panel_length_meter), precision("panel_qty", row));
		} else {
			row.panel_qty = 0;
		}
	}
}

textile.calculate_panel_length_meter = function(frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);

	if (row.panel_qty && row.panel_based_qty) {
		row.panel_length_meter = flt(row.stock_qty) / flt(row.panel_qty);
	} else {
		row.panel_length_meter = 0;
	}

	if (frm.doc.doctype == "Packing Slip") {
		frm.cscript.calculate_totals();
	} else {
		frm.cscript.calculate_taxes_and_totals();
	}
}

erpnext.taxes_and_totals_hooks.push(textile.calculate_panel_qty);
