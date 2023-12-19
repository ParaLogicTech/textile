frappe.provide("textile");

textile.TextileOrder = class TextileOrder extends frappe.ui.form.Controller {
	setup() {
		this.setup_queries();
	}

	refresh() {
		erpnext.toggle_naming_series();
		erpnext.hide_company();
	}

	setup_queries() {
		this.frm.set_query('customer', erpnext.queries.customer);

		for (let warehouse_field of ["fabric_warehouse", "source_warehouse", "wip_warehouse", "fg_warehouse"]) {
			this.frm.set_query(warehouse_field, () => {
				return erpnext.queries.warehouse(this.frm.doc);
			});
		}
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

	get_fabric_stock_qty(prefix) {
		let fabric_field = cstr(prefix) + "fabric_item";
		let qty_field = cstr(prefix) + "fabric_stock_qty";

		if (this.frm.doc[fabric_field] && this.frm.doc.fabric_warehouse) {
			return this.frm.call({
				method: "erpnext.stock.get_item_details.get_bin_details",
				args: {
					item_code: this.frm.doc[fabric_field],
					warehouse: this.frm.doc.fabric_warehouse,
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
}
