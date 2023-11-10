frappe.provide("textile");

frappe.ui.form.on("Work Order", {
	refresh: function (frm) {
		if (frm.doc.pretreatment_order) {
			frm.trigger("set_fabric_pretreatment_breadcrumbs");
		} else if (frm.doc.print_order) {
			frm.trigger("set_fabric_printing_breadcrumbs");
		}
	},

	set_fabric_pretreatment_breadcrumbs: function () {
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.set_workspace_breadcrumb({"workspace": "Fabric Pretreatment"});
		frappe.breadcrumbs.set_list_breadcrumb({"doctype": "Work Order"})
		frappe.breadcrumbs.set_form_breadcrumb({"doctype": "Work Order"}, "form");
	},

	set_fabric_printing_breadcrumbs: function () {
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.set_workspace_breadcrumb({"workspace": "Fabric Printing"});
		frappe.breadcrumbs.set_custom_breadcrumbs({"label": "Print Work Order", "route": "/app/print-work-order"});
		frappe.breadcrumbs.set_form_breadcrumb({"doctype": "Work Order"}, "form");
	},
});

textile.add_print_order_fields_in_work_order_prompt = function (doc, fields, purpose) {
	if (purpose != "Manufacture" || !doc.print_order) {
		return;
	}

	let qty_index = fields.findIndex(d => d.fieldname == "qty");
	fields.splice(qty_index+1, 0, {
		label: __("Printer"),
		fieldname: "fabric_printer",
		fieldtype: "Link",
		options: "Fabric Printer",
		send_to_stock_entry: true,
		reqd: 1,
		get_query: () => {
			return {
				filters: {
					process_item: doc.process_item || undefined,
				}
			}
		}
	});

	let work_order_index = fields.findIndex(d => d.fieldname == "work_order");
	fields.splice(work_order_index, 0, {
		label: __("Print Order"),
		fieldname: "print_order",
		fieldtype: "Link",
		options: "Print Order",
		read_only: 1,
		default: doc.print_order,
	});

	fields.push({
		label: __("Process"),
		fieldname: "process_item_name",
		fieldtype: "Data",
		read_only: 1,
		default: doc.process_item_name,
	});
}

textile.add_pretreatment_order_fields_in_work_order_prompt = function (doc, fields, purpose) {
	if (!doc.pretreatment_order) {
		return;
	}

	let work_order_index = fields.findIndex(d => d.fieldname == "work_order");
	fields.splice(work_order_index, 0, {
		label: __("Pretreatment Order"),
		fieldname: "pretreatment_order",
		fieldtype: "Link",
		options: "Pretreatment Order",
		read_only: 1,
		default: doc.pretreatment_order,
	});
}

textile.add_print_order_fields_in_finish_work_order_prompt = function (doc, fields) {
	if (doc && doc.work_orders && !doc.work_orders.every(d => d.print_order)) {
		return;
	}

	let process_item = [...new Set(doc.work_orders.map(d => d.process_item))];
	if (process_item.length && process_item.length > 1) {
		frappe.throw(__("All Work Orders must have same Process Item"));
	}

	let process_item_name = doc.work_orders.find(d => d.process_item == process_item[0]);
	process_item_name = process_item_name?.process_item_name;
	doc.process_item_name = process_item_name;

	let additional_fields = [
		{
			label: __("Printer"),
			fieldname: "fabric_printer",
			fieldtype: "Link",
			options: "Fabric Printer",
			send_to_stock_entry: true,
			reqd: 1,
			get_query: () => {
				return {
					filters: {
						process_item: process_item[0] || undefined,
					}
				}
			}
		},
		{
			fieldname: "cb_1",
			fieldtype: "Column Break",
		},
		{
			label: __("Process"),
			fieldname: "process_item_name",
			fieldtype: "Data",
			read_only: 1,
		},
		{
			fieldname: "sb_1",
			fieldtype: "Section Break",
		}
	]

	fields.unshift(...additional_fields);

	let work_orders_table = fields.find(d => d.fieldname == "work_orders");

	let work_order_idx = work_orders_table.fields.findIndex(d => d.fieldname == "work_order");
	let work_order_df = work_orders_table.fields.find(d => d.fieldname == "work_order");

	work_orders_table.fields.splice(work_order_idx+1, 0, {
		label: __("Print Order"),
		fieldname: "print_order",
		fieldtype: "Link",
		options: "Print Order",
		read_only: 1,
		in_list_view: 1,
		columns: 2,
		reqd: 1,
	});

	work_order_df.in_list_view = 0;
}

erpnext.manufacturing.stock_entry_qty_prompt_hooks.push(textile.add_print_order_fields_in_work_order_prompt);
erpnext.manufacturing.stock_entry_qty_prompt_hooks.push(textile.add_pretreatment_order_fields_in_work_order_prompt);
erpnext.manufacturing.job_card_qty_prompt_hooks.push(textile.add_pretreatment_order_fields_in_work_order_prompt);
erpnext.manufacturing.multiple_work_orders_qty_prompt_hooks.push(textile.add_print_order_fields_in_finish_work_order_prompt);
