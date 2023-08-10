frappe.provide("textile");

textile.add_print_order_fields_in_work_order_prompt = function (doc, purpose, fields) {
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

textile.add_print_order_fields_in_finish_work_order_prompt = function (doc, fields) {
	if (doc && doc.work_orders && !doc.work_orders.every(d => d.print_order)) {
		return;
	}

	let process_item = [...new Set(doc.work_orders.map(d => d.process_item))];

	if (process_item.length > 1) {
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

	let work_order_df = fields.find(d => d.fieldname == "work_orders");
	let work_order_index = work_order_df.fields.findIndex(d => d.fieldname == "work_order");
	work_order_df.fields.splice(work_order_index+1, 0, {
		label: __("Print Order"),
		fieldname: "print_order",
		fieldtype: "Link",
		options: "Print Order",
		read_only: 1,
		in_list_view: 1,
	});
}

erpnext.manufacturing.finish_work_orders_qty_prompt_hooks.push(textile.add_print_order_fields_in_finish_work_order_prompt);
erpnext.manufacturing.work_order_qty_prompt_hooks.push(textile.add_print_order_fields_in_work_order_prompt);
