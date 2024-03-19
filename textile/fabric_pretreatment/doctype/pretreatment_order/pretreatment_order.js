// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("textile");

textile.PretreatmentOrder = class PretreatmentOrder extends textile.TextileOrder {
	setup() {
		super.setup();

		this.frm.custom_make_buttons = {
			'Sales Order': 'Sales Order',
			'Work Order': 'Work Order',
			'Packing Slip': 'Packing Slip',
			'Delivery Note': 'Delivery Note',
			'Sales Invoice': 'Sales Invoice',
			'Print Order': 'Print Order',
		}
	}

	refresh() {
		super.refresh();
		this.setup_buttons();
		this.setup_route_options();
		this.set_default_warehouse();
		this.set_default_cost_center();
		this.frm.trigger('set_disallow_on_submit_fields_read_only');
		this.setup_progressbars();
	}

	setup_queries() {
		super.setup_queries();

		this.frm.set_query("greige_fabric_item", () => {
			let filters = {
				'textile_item_type': 'Greige Fabric',
			}
			if (this.frm.doc.is_fabric_provided_by_customer) {
				filters.customer = this.frm.doc.customer;
			}
			return erpnext.queries.item(filters);
		});

		this.frm.set_query("ready_fabric_item", () => {
			let filters = {
				'textile_item_type': 'Ready Fabric',
			}
			if (this.frm.doc.is_fabric_provided_by_customer) {
				filters.customer = this.frm.doc.customer;
			}
			return erpnext.queries.item(filters);
		});

		for (let [component_item_field, component_type] of Object.entries(textile.pretreatment_components)) {
			this.frm.set_query(component_item_field, () => {
				let filters = {
					textile_item_type: 'Process Component',
					process_component: component_type
				};
				return erpnext.queries.item(filters);
			});
		}
	}

	setup_route_options() {
		let greige_fabric_field = this.frm.get_docfield("greige_fabric_item");
		greige_fabric_field.get_route_options_for_new_doc = () => {
			let route_options = {
				is_customer_provided_item: this.frm.doc.is_fabric_provided_by_customer,
			}
			if (this.frm.doc.is_fabric_provided_by_customer && this.frm.doc.customer) {
				route_options["customer"] = this.frm.doc.customer;
			}
			return route_options;
		}

		let ready_fabric_field = this.frm.get_docfield("ready_fabric_item");
		ready_fabric_field.get_route_options_for_new_doc = () => {
			let route_options = {
				is_customer_provided_item: this.frm.doc.is_fabric_provided_by_customer,
			}
			if (this.frm.doc.is_fabric_provided_by_customer && this.frm.doc.customer) {
				route_options["customer"] = this.frm.doc.customer;
			}
			if (this.frm.doc.greige_fabric_item) {
				route_options["greige_fabric_item"] = this.frm.doc.greige_fabric_item;
			}
			return route_options;
		}
	}

	setup_buttons() {
		let doc = this.frm.doc;

		if (doc.docstatus == 1) {
			if (doc.__onload?.work_order) {
				this.frm.add_custom_button(__('Open Work Order'), () => {
					return frappe.set_route("Form", "Work Order", doc.__onload.work_order);
				});
			}

			if (this.frm.has_perm("submit")) {
				if (doc.status == "Closed") {
					this.frm.add_custom_button(__('Re-Open'), () => this.update_status("Re-Opened"), __("Status"));
				} else if(doc.status != "Completed") {
					this.frm.add_custom_button(__('Close'), () => this.update_status("Closed"), __("Status"));
				}
			}

			let can_create_sales_order = false;
			let can_create_work_order = false;
			let has_start_permission = frappe.model.can_write("Pretreatment Order");

			let bom_created = doc.ready_fabric_bom;
			if (!bom_created && has_start_permission) {
				this.frm.add_custom_button(__('Ready Fabric BOM'), () => this.create_ready_fabric_bom(),
					__("Create"));
			}

			let qty_precision = precision("stock_qty");

			let is_unpacked = doc.delivery_required
				&& flt(doc.produced_qty, qty_precision)
				&& flt(doc.packed_qty, qty_precision) < flt(doc.produced_qty, qty_precision);

			let is_undelivered = doc.delivery_required
				&& flt(doc.produced_qty, qty_precision)
				&& flt(doc.delivered_qty, qty_precision) < flt(doc.produced_qty, qty_precision)
				&& (!doc.packing_slip_required || flt(doc.delivered_qty, qty_precision) < flt(doc.packed_qty, qty_precision));

			if (doc.status != "Closed") {
				if (!doc.is_internal_customer && flt(doc.per_ordered) < 100) {
					can_create_sales_order = true;

					if (frappe.model.can_create("Sales Order")) {
						this.frm.add_custom_button(__('Sales Order'), () => this.make_sales_order(),
							__("Create"));
					}
				}

				if (
					bom_created
					&& (
						(!doc.is_internal_customer && doc.per_ordered && doc.per_work_ordered < doc.per_ordered)
						|| (doc.is_internal_customer && flt(doc.per_work_ordered) < 100)
					)
				) {
					can_create_work_order = true;
					if (frappe.model.can_create("Work Order") || has_start_permission) {
						this.frm.add_custom_button(__('Work Order'), () => this.create_work_order(),
							__("Create"));
					}
				}

				if (is_unpacked && frappe.model.can_create("Packing Slip")) {
					let packing_slip_btn = this.frm.add_custom_button(__("Packing Slip"), () => this.make_packing_slip());
					if (doc.packing_status != "Packed") {
						$(packing_slip_btn).removeClass("btn-default").addClass("btn-primary");
					}
				}

				if (is_undelivered && frappe.model.can_create("Delivery Note")) {
					let delivery_note_btn = this.frm.add_custom_button(__("Delivery Note"), () => this.make_delivery_note());

					if (
						(doc.packing_slip_required && doc.packing_status == "Packed")
						|| (!doc.packing_slip_required && doc.production_status == "Produced")
					) {
						$(delivery_note_btn).removeClass("btn-default").addClass("btn-primary");
					}
				}
			}

			if (doc.status != "Closed" && has_start_permission) {
				if (!bom_created || can_create_sales_order || can_create_work_order) {
					let start_btn = this.frm.add_custom_button(__("Quick Start"), () => this.start_pretreatment_order());
					$(start_btn).removeClass("btn-default").addClass("btn-primary");
				}

				if (!this.frm.doc.is_internal_customer && frappe.model.can_create("Print Order")) {
					this.frm.add_custom_button(__("Print Order"), () => this.make_print_order(), __("Create"));
				}
			}
		}
	}

	set_default_warehouse() {
		if (this.frm.is_new()) {
			const order_to_settings_field_map = {
				'fabric_warehouse': 'default_pretreatment_fabric_warehouse',
				'source_warehouse': 'default_pretreatment_source_warehouse',
				'wip_warehouse': 'default_pretreatment_wip_warehouse',
				'fg_warehouse': 'default_pretreatment_fg_warehouse',
			}

			for (let [order_field, settings_field] of Object.entries(order_to_settings_field_map)) {
				let warehouse = frappe.defaults.get_default(settings_field);
				if (!this.frm.doc[order_field] && warehouse) {
					this.frm.set_value(order_field, warehouse);
				}
			}
		}
	}

	set_default_cost_center() {
		if (this.frm.is_new()) {
			let default_cost_center = frappe.defaults.get_default("default_pretreatment_cost_center");
			if (default_cost_center && !this.frm.doc.cost_center) {
				this.frm.set_value("cost_center", default_cost_center);
			}
		}
	}

	setup_progressbars() {
		if (this.frm.doc.docstatus == 1 && this.frm.doc.per_work_ordered) {
			this.show_progress_for_production();
			this.show_progress_for_packing();
			this.show_progress_for_delivery();
		}
	}

	show_progress_for_production() {
		if (this.frm.doc.__onload?.progress_data) {
			erpnext.manufacturing.show_progress_for_production(this.frm.doc.__onload.progress_data, this.frm);

			for (let row of this.frm.doc.__onload.progress_data.operations || []) {
				erpnext.manufacturing.show_progress_for_operation(this.frm.doc.__onload.progress_data, row, this.frm);
			}
		}
	}

	show_progress_for_packing() {
		let produced_qty = this.frm.doc.produced_qty;
		if (!produced_qty || !this.frm.doc.delivery_required || !this.frm.doc.packing_slip_required) {
			return;
		}

		let packed_qty = this.frm.doc.packed_qty;
		let to_pack_qty = produced_qty - packed_qty;
		to_pack_qty = Math.max(to_pack_qty, 0);

		erpnext.utils.show_progress_for_qty({
			frm: this.frm,
			title: __('Packing Status'),
			total_qty: this.frm.doc.stock_qty,
			progress_bars: [
				{
					title: __('<b>Packed:</b> {0} {1} ({2}%)', [
						format_number(packed_qty),
						"Meter",
						format_number(packed_qty / this.frm.doc.stock_qty * 100, null, 1),
					]),
					completed_qty: packed_qty,
					progress_class: "progress-bar-success",
					add_min_width: 0.5,
				},
				{
					title: __("<b>Ready to Pack:</b> {0} {1}", [format_number(to_pack_qty), "Meter"]),
					completed_qty: to_pack_qty,
					progress_class: "progress-bar-warning",
				},
			],
		});
	}

	show_progress_for_delivery() {
		if (!this.frm.doc.delivery_required) {
			return;
		}

		let produced_qty = this.frm.doc.produced_qty;
		let packed_qty = this.frm.doc.packed_qty;
		let deliverable_qty = this.frm.doc.packing_slip_required ? packed_qty : produced_qty;
		if (!deliverable_qty) {
			return;
		}

		let delivered_qty = this.frm.doc.delivered_qty;
		let to_deliver = deliverable_qty - delivered_qty;
		to_deliver = Math.max(to_deliver, 0);

		erpnext.utils.show_progress_for_qty({
			frm: this.frm,
			title: __('Delivery Status'),
			total_qty: this.frm.doc.stock_qty,
			progress_bars: [
				{
					title: __('<b>Delivered:</b> {0} {1} ({2}%)', [
						format_number(delivered_qty),
						"Meter",
						format_number(delivered_qty / this.frm.doc.stock_qty * 100, null, 1),
					]),
					completed_qty: delivered_qty,
					progress_class: "progress-bar-success",
					add_min_width: 0.5,
				},
				{
					title: __("<b>Ready to Deliver:</b> {0} {1}", [format_number(to_deliver), "Meter"]),
					completed_qty: to_deliver,
					progress_class: "progress-bar-warning",
				},
			],
		});
	}

	customer() {
		this.get_is_internal_customer();
	}

	company() {
		this.get_is_internal_customer();
	}

	is_internal_customer() {
		if (this.frm.doc.is_internal_customer) {
			this.frm.set_value({
				is_fabric_provided_by_customer: 0,
				delivery_required: 0,
			});
		}
	}

	greige_fabric_item() {
		this.get_fabric_stock_qty("greige_");
		this.get_fabric_item_details("greige_", true, false, true);
	}

	ready_fabric_item() {
		this.get_fabric_item_details("ready_", false, true, false);
	}

	fabric_warehouse() {
		this.get_fabric_stock_qty("greige_");
	}

	get_fabric_item_details(prefix, get_ready_fabric, get_greige_fabric, get_default_process) {
		let fabric_field = cstr(prefix) + "fabric_item";

		if (this.frm.doc[fabric_field]) {
			return this.frm.call({
				method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.get_fabric_item_details",
				args: {
					fabric_item: this.frm.doc[fabric_field],
					prefix: prefix,
					get_ready_fabric: cint(get_ready_fabric),
					get_greige_fabric: cint(get_greige_fabric),
					get_default_process: cint(get_default_process),
				},
				callback: (r) => {
					if (r.message) {
						this.frm.set_value(r.message);
					}
				}
			});
		}
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

	update_status(status) {
		this.frm.check_if_unsaved();

		frappe.ui.form.is_saving = true;
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.update_status",
			args: {
				pretreatment_order: this.frm.doc.name,
				status: status
			},
			callback: (r) => {
				this.frm.reload_doc();
			},
			always: () => {
				frappe.ui.form.is_saving = false;
			}
		});
	}

	start_pretreatment_order() {
		frappe.confirm(
			__("Are you sure you want to start this Pretreatment Order? Quick starting will create Ready Fabric BOM, Sales Order and Work Order"),
			() => {
				return this._start_pretreatment_order();
			}
		);
	}

	_start_pretreatment_order() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.start_pretreatment_order",
			args: {
				pretreatment_order: this.frm.doc.name,
			},
			freeze: true,
			callback: (r) => {
				if (!r.exc) {
					this.frm.reload_doc();
				}
			}
		});
	}

	create_ready_fabric_bom() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.create_ready_fabric_bom",
			args: {
				pretreatment_order: this.frm.doc.name
			},
			freeze: true,
			callback: (r) => {
				if (!r.exc) {
					this.frm.reload_doc();
				}
			}
		});
	}

	make_sales_order() {
		frappe.model.open_mapped_doc({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_sales_order",
			frm: this.frm
		});
	}

	create_work_order() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.create_work_order",
			args: {
				pretreatment_order: this.frm.doc.name
			},
			freeze: true,
			callback: (r) => {
				if (!r.exc) {
					this.frm.reload_doc();
				}
			}
		});
	}

	make_packing_slip() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_packing_slip",
			args: {
				source_name: this.frm.doc.name,
			},
			callback: function (r) {
				if (!r.exc) {
					let doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			}
		});
	}

	make_delivery_note() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_delivery_note",
			args: {
				source_name: this.frm.doc.name,
			},
			callback: function (r) {
				if (!r.exc) {
					let doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			}
		});
	}

	make_print_order() {
		return frappe.call({
			method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_print_order",
			args: {
				source_name: this.frm.doc.name,
			},
			callback: function (r) {
				if (!r.exc) {
					let doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			}
		});
	}
}

extend_cscript(cur_frm.cscript, new textile.PretreatmentOrder({frm: cur_frm}));
