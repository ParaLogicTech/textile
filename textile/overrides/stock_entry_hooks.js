frappe.ui.form.on('Stock Entry', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Print Order Fabrics'), function() {
				frm.events.get_items_from_print_order(frm);
			}, __("Get Items From"));
		}
	},

	get_items_from_print_order(frm) {
		erpnext.utils.map_current_doc({
			method: "textile.fabric_printing.doctype.print_order.print_order.make_customer_fabric_stock_entry",
			source_doctype: "Print Order",
			target: frm,
			setters: [
				{
					fieldtype: 'Link',
					label: __('Customer'),
					options: 'Customer',
					fieldname: 'customer',
					default: frm.doc.customer || undefined,
				},
			],
			columns: ['customer_name', 'fabric_item_name', 'process_item_name', 'transaction_date'],
			get_query_filters: {
				docstatus: 1,
				status: ["!=", "Closed"],
				per_produced: ["<", 99.99],
				company: frm.doc.company,
				customer: frm.doc.customer || undefined,
			}
		});
	}
});
