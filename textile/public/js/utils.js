frappe.provide("textile");

textile.printing_components = {
	"coating_item": "Coating",
	"softener_item": "Softener",
	"sublimation_paper_item": "Sublimation Paper",
	"protection_paper_item": "Protection Paper",
}

textile.pretreatment_components = {
	"singeing_item": "Singeing",
	"desizing_item": "Desizing",
	"bleaching_item": "Bleaching",
}

textile.process_components = Object.assign({}, textile.printing_components, textile.pretreatment_components);

$.extend(textile, {
	get_items_from_print_order: function (frm, method, filters, query) {
		let query_filters = {
			docstatus: 1,
			status: ["!=", "Closed"],
			items_created: 1,
			company: frm.doc.company,
			customer: frm.doc.customer || undefined,
		}
		if (filters) {
			Object.assign(query_filters, filters);
		}

		erpnext.utils.map_current_doc({
			method: method,
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
						return erpnext.queries.item({ textile_item_type: 'Ready Fabric' });
					},
				},
				{
					fieldtype: 'Link',
					label: __('Process Item'),
					options: 'Item',
					fieldname: 'process_item',
					get_query: () => {
						return erpnext.queries.item({ textile_item_type: 'Print Process' });
					},
				},
			],
			columns: ['customer_name', 'fabric_item_name', 'process_item_name', 'transaction_date'],
			get_query: () => {
				return {
					query: query,
					filters: query_filters,
				}
			},
		});
	},

	get_textile_conversion_factors: function () {
		return {
			inch_to_meter: flt(frappe.defaults.get_global_default("inch_to_meter")) || 0.0254,
			yard_to_meter: flt(frappe.defaults.get_global_default("yard_to_meter")) || 0.9144,
			meter_to_meter: 1
		}
	}
});
