frappe.ui.form.on('Customer', {
	default_printing_uom(frm) {
		if (frm.doc.default_printing_uom == "Panel") {
			frm.set_value("default_printing_qty_type", "Print Qty");
		} else {
			frm.set_value("default_printing_length_uom", frm.doc.default_printing_uom);
		}
	}
});
