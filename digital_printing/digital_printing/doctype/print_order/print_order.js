// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("erpnext.digital_printing");

erpnext.digital_printing.PrintOrder = class PrintOrder extends frappe.ui.form.Controller {

	conversion_factors = {
		inch_to_meter: 0.0254,
		yard_to_meter: 0.9144,
		meter_to_meter: 1
	}

	setup() {
		this.setup_queries();
	}

	refresh() {
		erpnext.hide_company();
		this.setup_buttons();
	}

	on_upload_complete() {
		return this.get_items_from_attachments();
	}

	setup_queries() {
		this.frm.set_query("fabric_item", () => {
			let filters = {
				'print_item_type': 'Fabric'
			}
			if (this.frm.doc.is_fabric_provided_by_customer) {
				filters.customer = this.frm.doc.customer;
			}
			return erpnext.queries.item(filters);
		});

		this.frm.set_query("process_item", () => {
			return erpnext.queries.item({ print_item_type: 'Print Process' });
		});
	}

	setup_buttons() {
		if (this.frm.doc.docstatus == 1 && this.frm.doc.items.filter(d => !d.item_code)) {
			this.frm.add_custom_button(__('Create Items'), () => this.create_printed_design_item(),
				__("Create"));
		}
	}

	default_gap() {
		this.override_default_value_in_items('design_gap');
	}

	default_qty() {
		this.override_default_value_in_items('qty');
	}

	default_uom() {
		this.override_default_value_in_items('uom');
		if (this.frm.doc.default_uom == "Panel") {
			this.frm.set_value("default_qty_type", "Print Qty");
		} else {
			this.frm.set_value("default_length_uom", this.frm.doc.default_uom);
		}
	}

	default_qty_type() {
		this.override_default_value_in_items('qty_type');
	}

	default_wastage() {
		this.override_default_value_in_items('per_wastage');
	}

	default_length_uom() {
		this.override_default_value_in_items('length_uom');
	}

	items_add(doc, cdt, cdn) {
		this.set_default_values_in_item(cdt, cdn);
	}

	before_items_remove(doc, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		let file_name = this.frm.attachments.get_file_id_from_file_url(row.design_image);
		this.frm.attachments.remove_attachment(file_name);
		this.calculate_totals();
	}

	design_image(doc, cdt, cdn) {
		var me = this;
		let row = frappe.get_doc(cdt, cdn);

		return frappe.call({
			method: "get_image_details",
			args: {
				image_url: row.design_image
			},
			doc: me.frm.doc,
			callback: function(r) {
				if (!r.exc && r.message) {
					return frappe.model.set_value(cdt, cdn, r.message);
				}
			}
		});
	}

	design_gap() {
		this.calculate_totals();
	}

	qty() {
		this.calculate_totals();
	}

	uom(doc, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);

		if (row.uom == 'Panel') {
			frappe.model.set_value(cdt, cdn, "qty_type", "Print Qty");
		} else {
			frappe.model.set_value(cdt, cdn, "length_uom", row.uom);
		}
		this.calculate_totals();
	}

	qty_type() {
		this.calculate_totals();
	}

	per_wastage() {
		this.calculate_totals();
	}

	length_uom() {
		this.calculate_totals();
	}

	override_default_value_in_items(cdf) {
		(this.frm.doc.items || []).forEach(d => {
			this.set_default_values_in_item(d.doctype, d.name, cdf);
		});
	}

	set_default_values_in_item(cdt, cdn, cdf=null) {
		let defaults = {
			'design_gap': this.frm.doc.default_gap,
			'qty': this.frm.doc.default_qty,
			'uom': this.frm.doc.default_uom,	
			'qty_type': this.frm.doc.default_qty_type,
			'per_wastage': this.frm.doc.default_wastage,
			'length_uom': this.frm.doc.default_length_uom,
		}

		if (cdf) {
			if (defaults[cdf]) {
				frappe.model.set_value(cdt, cdn, cdf, defaults[cdf]);
			}
		} else {
			for (const [key, value] of Object.entries(defaults)) {
				if (value) {
					frappe.model.set_value(cdt, cdn, key, value);
				}
			}
		}
	}

	calculate_totals = () => {
		this.frm.doc.total_print_length = 0;
		this.frm.doc.total_fabric_length = 0;
		this.frm.doc.total_panel_qty = 0;

		this.frm.doc.items.forEach(d => {
			frappe.model.round_floats_in(d);

			d.panel_length_inch = flt(d.design_height) + flt(d.design_gap);
			d.panel_length_meter = d.panel_length_inch * this.conversion_factors.inch_to_meter;
			d.panel_length_yard = d.panel_length_meter / this.conversion_factors.yard_to_meter;

			let waste = d.per_wastage / 100;
			let uom_to_convert = d.length_uom + '_to_' + d.stock_uom;
			let conversion_factor = this.conversion_factors[uom_to_convert.toLowerCase()] || 1;

			if (d.uom != "Panel") {
				d.print_length = d.qty_type == "Print Qty" ? d.qty : waste < 1 ? d.qty * (1 - waste) : 0;
				d.fabric_length = d.qty_type == "Fabric Qty" ? d.qty : waste < 1 ? d.qty / (1 - waste) : 0;
			} else {
				d.print_length = d.qty * d.panel_length_meter / conversion_factor;
				d.fabric_length = waste < 1 ? d.print_length / (1 - waste) : 0;
			}
			d.print_length = flt(d.print_length, precision("print_length", d));
			d.fabric_length = flt(d.fabric_length, precision("print_length", d));

			d.stock_print_length = d.print_length * conversion_factor;
			d.stock_fabric_length = d.fabric_length * conversion_factor;

			d.panel_qty = d.panel_length_meter ? d.stock_print_length / d.panel_length_meter : 0;
			d.panel_qty = flt(d.panel_qty, precision("panel_qty", d));

			this.frm.doc.total_print_length += d.stock_print_length;
			this.frm.doc.total_fabric_length += d.stock_fabric_length;
			this.frm.doc.total_panel_qty += d.panel_qty;
		});

		this.frm.doc.total_print_length = flt(this.frm.doc.total_print_length, precision("total_print_length"));
		this.frm.doc.total_fabric_length = flt(this.frm.doc.total_fabric_length, precision("total_fabric_length"));
		this.frm.doc.total_panel_qty = flt(this.frm.doc.total_panel_qty, precision("total_panel_qty"));

		this.frm.debounced_refresh_fields();
	}

	get_items_from_attachments = frappe.utils.debounce(() => {
		var me = this;
		return frappe.call({
			method: "on_upload_complete",
			doc: me.frm.doc,
			callback: function(r) {
				if (!r.exc) {
					me.calculate_totals();
				}
			}
		});
	}, 1000);

	create_printed_design_item() {
		let me = this;

		return frappe.call({
			method: "create_printed_design_item",
			doc: me.frm.doc,
			freeze: true,
			callback: function(r) {
				if (!r.exc) {
					frappe.msgprint(__("Printed Design Items created successfully."))
					me.frm.reload_doc();
				}
			}
		});
	}
};

extend_cscript(cur_frm.cscript, new erpnext.digital_printing.PrintOrder({frm: cur_frm}));
