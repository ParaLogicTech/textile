frappe.provide("digital_printing");

digital_printing.calculate_panel_qty = function() {
	if (
		!frappe.meta.has_field(this.frm.doc.doctype + " Item", 'panel_length_meter')
		|| !frappe.meta.has_field(this.frm.doc.doctype + " Item", 'panel_qty')
	) {
		return;
	}

	for (let row of this.frm.doc.items || []) {
		if (row.panel_length_meter) {
			row.panel_qty = flt(row.stock_qty / row.panel_length_meter, precision("panel_qty", row));
		} else {
			row.panel_qty = 0;
		}
	}

}

erpnext.taxes_and_totals_hooks.push(digital_printing.calculate_panel_qty);
