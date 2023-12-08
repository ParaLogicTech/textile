// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("textile");

textile.CoatingOrder = class CoatingOrder extends textile.TextileOrder {
	refresh() {
		super.refresh();
		this.setup_buttons();
		this.show_progress_for_coating();
	}

	setup_queries() {
		super.setup_queries();

		this.frm.set_query("fabric_item", () => {
			let filters = {
				'textile_item_type': 'Ready Fabric',
			}
			return erpnext.queries.item(filters);
		});

		this.frm.set_query("coating_item", () => {
			let filters = {
				'textile_item_type': 'Process Component',
				'process_component': 'Coating',
			}
			return erpnext.queries.item(filters);
		});
	}

	setup_buttons() {
		if (this.frm.doc.docstatus == 1 && flt(this.frm.doc.per_coated) < 100) {
			let finish_button = this.frm.add_custom_button(__("Finish"), () => this.finish_coating_order());
			finish_button.removeClass("btn-default").addClass("btn-primary");
		}
	}

	customer() {
		this.get_is_internal_customer();
	}

	company() {
		this.get_is_internal_customer();
	}


	fabric_item() {
		this.get_fabric_stock_qty();
		this.get_fabric_item_details();
	}

	fabric_warehouse() {
		this.get_fabric_stock_qty();
	}

	coating_item() {
		this.get_default_coating_bom();
	}

	qty() {
		this.calculate_totals();
	}

	uom() {
		this.calculate_totals();
	}

	calculate_totals() {
		frappe.model.round_floats_in(this.frm.doc);

		let conversion_factors = textile.get_textile_conversion_factors();
		let uom_to_convert = this.frm.doc.uom + '_to_' + this.frm.doc.stock_uom;
		uom_to_convert = uom_to_convert.toLowerCase();
		let conversion_factor = conversion_factors[uom_to_convert] || 1;

		this.frm.doc.stock_qty = this.frm.doc.qty * conversion_factor;

		this.frm.refresh_fields();
	}

	get_fabric_stock_qty() {
		if (this.frm.doc.fabric_item && this.frm.doc.fabric_warehouse) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_bin_details",
				args: {
					item_code: this.frm.doc.fabric_item,
					warehouse: this.frm.doc.fabric_warehouse,
				},
				callback: (r) => {
					if (r.message) {
						this.frm.set_value("fabric_stock_qty", flt(r.message.actual_qty));
					}
				}
			});
		} else {
			this.frm.set_value('fabric_stock_qty', 0);
		}
	}

	get_fabric_item_details() {
		if (this.frm.doc.fabric_item) {
			return this.frm.call({
				method: "textile.fabric_printing.doctype.print_order.print_order.get_fabric_item_details",
				args: {
					fabric_item: this.frm.doc.fabric_item,
					get_default_process: 1
				},
				callback: (r) => {
					if (r.message) {
						this.frm.set_value(r.message);
					}
				}
			});
		}
	}

	get_default_coating_bom() {
		return this.frm.call({
			method: "textile.fabric_printing.doctype.coating_order.coating_order.get_default_coating_bom",
			args: {
				coating_item: this.frm.doc.coating_item,
			},
			callback: (r) => {
				if (r.message) {
					this.frm.set_value(r.message);
				}
			}
		});
	}

	finish_coating_order() {
		let doc = this.frm.doc;
		let max = flt(doc.stock_qty) - flt(doc.coated_qty);

		let fields = [
			{
				fieldtype: 'Float',
				label: __('Qty for Coating'),
				fieldname: 'qty',
				description: __('Max: {0}', [format_number(max)]),
				reqd: 1,
				default: max
			},
			{
				fieldtype: 'Column Break',
			},
			{
				label: __('Stock UOM'),
				fieldname: 'stock_uom',
				fieldtype: 'Data',
				default: doc.stock_uom,
				read_only: 1,
			},
			{
				fieldtype: 'Section Break',
			},
			{
				label: __('Qty to Coat'),
				fieldname: 'qty_to_coat',
				fieldtype: 'Float',
				default: flt(doc.stock_qty),
				read_only: 1,
			},
			{
				fieldtype: 'Column Break',
			},
			{
				label: __('Coated Qty'),
				fieldname: 'coated_qty',
				fieldtype: 'Float',
				default: flt(doc.coated_qty),
				read_only: 1,
			},
			{
				fieldtype: 'Section Break',
			},
			{
				label: __('Fabric Item'),
				fieldname: 'fabric_item',
				fieldtype: 'Link',
				options: "Item",
				default: doc.fabric_item,
				read_only: 1,
			},
			{
				label: __('Fabric Item Name'),
				fieldname: 'fabric_item_name',
				fieldtype: 'Data',
				default: doc.fabric_item_name,
				read_only: 1,
			},
			{
				fieldtype: 'Column Break',
			},
			{
				label: __('Coating Item'),
				fieldname: 'coating_item',
				fieldtype: 'Link',
				options: "Item",
				default: doc.coating_item,
				read_only: 1,
			},
			{
				label: __('Coating Item Name'),
				fieldname: 'coating_item_name',
				fieldtype: 'Data',
				default: doc.coating_item_name,
				read_only: 1,
			},
		];

		let dialog = new frappe.ui.Dialog({
			title: __("Coating"),
			fields: fields,
			static: true,
			primary_action: function() {
				let data = dialog.get_values();
				if (flt(data.qty) > max) {
					frappe.msgprint(__('Quantity can not be more than {0}', [format_number(max)]));
					return;
				}
				frappe.call({
					method: "textile.fabric_printing.doctype.coating_order.coating_order.make_stock_entry_from_coating_order",
					args: {
						"coating_order_id": doc.name,
						"qty": data.qty,
					},
					freeze: 1,
					callback: (r) => {
						if (r.message) {
							frappe.model.sync(r.message);

							if (cur_frm && cur_frm.doc.doctype == "Coating Order" && cur_frm.doc.name == doc.name) {
								cur_frm.reload_doc();
							}

							if (r.message.docstatus != 1) {
								frappe.set_route('Form', r.message.doctype, r.message.name);
							}
						}
					}
				});
				dialog.hide();
			},
			primary_action_label: __('Submit')
		});
		dialog.show();
	}

	show_progress_for_coating() {
		let me = this;

		if (me.frm.doc.docstatus == 1) {
			erpnext.utils.show_progress_for_qty({
				frm: me.frm,
				as_html: !me.frm,
				title: __('Coating Status'),
				total_qty: me.frm.doc.qty,
				progress_bars: [
					{
						title: __("<b>Coated:</b> {0} / {1} {2} ({3}%)", [
							format_number(me.frm.doc.coated_qty),
							format_number(me.frm.doc.stock_qty),
							me.frm.doc.stock_uom,
							format_number(me.frm.doc.stock_qty ? me.frm.doc.coated_qty / me.frm.doc.stock_qty * 100: 0, null, 1),
						]),
						completed_qty: me.frm.doc.coated_qty,
						progress_class: "progress-bar-success",
						add_min_width: me.frm.doc.stock_qty ? 0.5 : 0,
					},
					{
						title: __("<b>Coating Remaining:</b> {0} {1}", [format_number(me.frm.doc.stock_qty - me.frm.doc.coated_qty), me.frm.doc.stock_uom]),
						completed_qty: me.frm.doc.stock_qty - me.frm.doc.coated_qty,
						progress_class: "progress-bar-warning",
					},
				],
			});
		}
	}
};

extend_cscript(cur_frm.cscript, new textile.CoatingOrder({frm: cur_frm}));