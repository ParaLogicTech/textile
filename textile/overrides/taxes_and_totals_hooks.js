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

textile.set_printed_fabric_details = function () {
	if (!frappe.meta.has_field(this.frm.doc.doctype, "printed_fabrics")) {
		return;
	}

	// Group fabrics and calculate totals
	let fabric_summary = {}
	for (let item of this.frm.doc.items) {
		if (!item.fabric_item || !item.is_printed_fabric) {
			continue;
		}

		let empty_row = {
			"fabric_item": item.fabric_item,
			"fabric_item_name": item.fabric_item_name,
			"fabric_qty": 0,
			"fabric_rate": 0,
			"fabric_amount": 0,
		}

		let fabric_dict = fabric_summary[item.fabric_item];
		if (!fabric_dict) {
			fabric_dict = fabric_summary[item.fabric_item] = Object.assign({}, empty_row);
		}

		fabric_dict.fabric_qty += flt(item.stock_qty);
		fabric_dict.fabric_amount += flt(item.amount);
	}

	// Calculate Rate
	for (let fabric_dict of Object.values(fabric_summary)) {
		fabric_dict.fabric_rate = fabric_dict.fabric_qty ? fabric_dict.fabric_amount / fabric_dict.fabric_qty : 0;
	}

	// Update Rows
	const get_row = (fabric_item) => {
		let existing_rows = (this.frm.doc.printed_fabrics || []).filter(d => d.fabric_item == fabric_item);
		return existing_rows.length ? existing_rows[0] : null;
	}

	for (let fabric_dict of Object.values(fabric_summary)) {
		let row = get_row(fabric_dict.fabric_item);
		if (!row) {
			row = this.frm.add_child("printed_fabrics");
		}

		Object.assign(row, fabric_dict);
	}

	// Reset removed fabrics rows
	for (let printed_fabric_row of this.frm.doc.printed_fabrics || []) {
		if (!fabric_summary[printed_fabric_row.fabric_item]) {
			printed_fabric_row.fabric_qty = 0;
			printed_fabric_row.fabric_rate = 0;
			printed_fabric_row.fabric_amount = 0;
		}
	}
}

textile.set_printed_fabric_rate = function (frm, printed_fabric_row) {
	if (!printed_fabric_row.fabric_item) {
		return;
	}

	for (let d of frm.doc.items || []) {
		if (d.fabric_item == printed_fabric_row.fabric_item && d.is_printed_fabric) {
			d.rate = flt(printed_fabric_row.fabric_rate);
			frm.cscript.set_item_rate(d);
		}
	}
}

erpnext.taxes_and_totals_hooks.push(textile.calculate_panel_qty);
erpnext.taxes_and_totals_hooks.push(textile.set_printed_fabric_details);
