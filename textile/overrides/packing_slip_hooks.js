frappe.provide("textile");

frappe.ui.form.on("Packing Slip", {
	setup: function(frm) {
		frm.cscript.calculate_total_hooks.push(textile.calculate_panel_qty);
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Print Order'), function() {
				frm.events.get_items_from_print_order(frm);
			}, __("Get Items From"));
		}
	},

	get_items_from_print_order(frm) {
		erpnext.utils.map_current_doc({
			method: "textile.digital_printing.doctype.print_order.print_order.make_packing_slip",
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
				{
					fieldtype: 'Link',
					label: __('Fabric Item'),
					options: 'Item',
					fieldname: 'fabric_item',
					get_query: () => {
						return erpnext.queries.item({ print_item_type: 'Fabric' });
					},
				},
				{
					fieldtype: 'Link',
					label: __('Process Item'),
					options: 'Item',
					fieldname: 'process_item',
					get_query: () => {
						return erpnext.queries.item({ print_item_type: 'Print Process' });
					},
				},
			],
			columns: ['customer_name', 'fabric_item_name', 'process_item_name', 'transaction_date'],
			get_query_filters: {
				docstatus: 1,
				status: ["not in", ["Closed", "To Create Items"]],
				packing_status: "To Pack",
				company: frm.doc.company,
				customer: frm.doc.customer || undefined,
			}
		});
	},
});

frappe.ui.form.on("Packing Slip Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_totals();
	},
});
