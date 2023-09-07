// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("textile");

textile.PretreatmentOrder = class PretreatmentOrder extends frappe.ui.form.Controller {
	setup() {
		this.frm.custom_make_buttons = {
			'Sales Order': 'Sales Order',
			'Work Order': 'Work Order',
			'Packing Slip': 'Packing Slip',
			'Delivery Note': 'Delivery Note',
			'Sales Invoice': 'Sales Invoice',
		}

		this.setup_queries();
	}

	refresh() {
		erpnext.hide_company();
		this.setup_buttons();
		this.setup_route_options();
		this.set_default_warehouse();
		this.setup_progressbars();
	}

	setup_queries() {
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

		for (let warehouse_field of ["source_warehouse", "wip_warehouse", "fg_warehouse"]) {
			this.frm.set_query(warehouse_field, () => {
				return erpnext.queries.warehouse(this.frm.doc);
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

			let bom_created = doc.ready_fabric_bom;
			if (!bom_created) {
				this.frm.add_custom_button(__('Ready Fabric BOM'), () => this.create_ready_fabric_bom(),
					__("Create"));
			}

			if (doc.status != "Closed") {
				if (!doc.is_internal_customer && flt(doc.per_ordered) < 100) {
					this.frm.add_custom_button(__('Sales Order'), () => this.make_sales_order(),
						__("Create"));
				}

				if (bom_created && flt(doc.per_work_ordered) < 100) {
					this.frm.add_custom_button(__('Work Order'), () => this.create_work_order(),
						__("Create"));
				}
			}
		}
	}

	set_default_warehouse() {
		if (this.frm.is_new()) {
			const order_to_settings_field_map = {
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

	setup_progressbars() {

	}

	customer() {
		this.get_is_internal_customer();
	}

	company() {
		this.get_is_internal_customer();
	}

	get_is_internal_customer() {
		if (!this.frm.doc.customer || !this.frm.doc.company) {
			return this.frm.set_value("is_internal_customer", 0);
		} else {
			return frappe.call({
				method: "textile.utils.is_internal_customer",
				args: {
					customer: this.frm.doc.customer,
					company: this.frm.doc.company,
				},
				callback: (r) => {
					return this.frm.set_value("is_internal_customer", r.message);
				}
			});
		}
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
		this.get_fabric_item_details("greige_", true, false);
	}

	ready_fabric_item() {
		this.get_fabric_item_details("ready_", false, true);
	}

	source_warehouse() {
		this.get_fabric_stock_qty("greige_");
	}

	get_fabric_stock_qty(prefix) {
		let fabric_field = cstr(prefix) + "fabric_item";
		let qty_field = cstr(prefix) + "fabric_stock_qty";

		if (this.frm.doc[fabric_field] && this.frm.doc.source_warehouse) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_bin_details",
				args: {
					item_code: this.frm.doc[fabric_field],
					warehouse: this.frm.doc.source_warehouse,
				},
				callback: (r) => {
					if (r.message) {
						this.frm.set_value(qty_field, flt(r.message.actual_qty));
					}
				}
			});
		} else {
			this.frm.set_value(qty_field, 0);
		}
	}

	get_fabric_item_details(prefix, get_ready_fabric, get_greige_fabric) {
		let fabric_field = cstr(prefix) + "fabric_item";

		if (this.frm.doc[fabric_field]) {
			return this.frm.call({
				method: "textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.get_fabric_item_details",
				args: {
					fabric_item: this.frm.doc[fabric_field],
					prefix: prefix,
					get_ready_fabric: cint(get_ready_fabric),
					get_greige_fabric: cint(get_greige_fabric),
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
}

extend_cscript(cur_frm.cscript, new textile.PretreatmentOrder({frm: cur_frm}));
