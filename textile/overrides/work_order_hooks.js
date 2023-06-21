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

erpnext.manufacturing.work_order_qty_prompt_hooks.push(textile.add_print_order_fields_in_work_order_prompt);
