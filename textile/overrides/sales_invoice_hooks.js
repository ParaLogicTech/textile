frappe.provide("textile");

frappe.ui.form.on("Sales Invoice", {
	setup: function (frm) {
		if (frm.fields_dict.printed_fabrics?.grid) {
			frm.fields_dict.printed_fabrics.grid.cannot_add_rows = 1;
		}
	},

	refresh: function (frm) {
		frm.add_custom_button(__('Pretreatment Order'), function() {
			textile.get_items_from_pretreatment_order(
				frm,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_sales_invoice",
				null,
				"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.get_pretreatment_orders_to_be_billed"
			);
		}, __("Get Items From"));
	},

	onload: function(listview) {
		pricing_dialogue(listview, "Check Printing Rate", "textile.fabric_printing.doctype.print_pricing_rule.print_pricing_rule.get_printing_rate_breakup");
		pricing_dialogue(listview, "Check Pretreatment Rate", "textile.fabric_pretreatment.doctype.pretreatment_pricing_rule.pretreatment_pricing_rule.get_pretreatment_rate_breakup");
	}
});

frappe.ui.form.on("Sales Invoice Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_taxes_and_totals();
	},
});

frappe.ui.form.on("Printed Fabric Detail", {
	fabric_rate: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		textile.set_printed_fabric_rate(frm, row);
		frm.cscript.calculate_taxes_and_totals();
	},

	before_printed_fabrics_remove: function(frm, cdt, cdn) {
		var printed_fabrics_rows_selected = frm.get_selected().printed_fabrics
		var printed_fabrics_removed = [];
		for (let i in printed_fabrics_rows_selected) {
			printed_fabrics_removed.push.apply(printed_fabrics_removed, (frm.doc.printed_fabrics).filter(d => d.name === printed_fabrics_rows_selected[i]))
		}
		
		var parent_field = frm.get_field('items');
		for (let i in printed_fabrics_removed) {
			if (parent_field) {
				var rows = (frm.doc.items || []).filter(d => d.fabric_item === printed_fabrics_removed[i].fabric_item);
				$.each(rows, function (i, row) {
					let grid_row = parent_field.grid.grid_rows_by_docname[row.name];
					if (grid_row) {
						grid_row.remove();
					}
				});
			}	
		}
	}
});

var pricing_dialogue = function(listview, title, method_path) {
	listview.page.add_menu_item(__(title), () => {
		let doc = {
			price_list: frappe.defaults.get_global_default("selling_price_list"),
			applied_rules: [],
		};

		let base_rate_field_name = title ==='Check Printing Rate' ? "base_printing_rate" : "base_pretreatment_rate";
		let base_rate_field_label = title ==='Check Printing Rate' ? "Base Printing Rate" : "Base Pretreatment Rate";
		let rate_field_name = title ==='Check Printing Rate' ? "printing_rate" : "pretreatment_rate";
		let rate_field_label = title ==='Check Printing Rate' ? "Printing Rate" : "Pretreatment Rate";

		const get_price = () => {
			if (doc.price_list && doc.fabric_item) {
				return frappe.call({
					method: method_path,
					args: {
						item_code: doc.fabric_item,
						price_list: doc.price_list,
						customer: doc.customer
					},
					callback: (r) => {
						if (r.message) {							
							if (title === 'Check Printing Rate') {
								doc.base_printing_rate = r.message.base_rate;
								doc.printing_rate = r.message.rule_rate;
							} else {
								doc.base_pretreatment_rate = r.message.base_rate;
								doc.pretreatment_rate = r.message.rule_rate;
							}
							doc.fabric_rate = r.message.fabric_rate;
							doc.price_list_rate = r.message.price_list_rate;
							doc.applied_rules = r.message.applied_rules || [];
							dialog.refresh();
						}
					}
				});
			} else {
				if (title === 'Check Printing Rate') {
					doc.base_printing_rate = null;
					doc.printing_rate = null;
				} else {
					doc.base_pretreatment_rate = null;
					doc.pretreatment_rate = null;
				}
				doc.fabric_rate = null;
				doc.price_list_rate = null;
				doc.applied_rules = [];
				dialog.refresh();
			}
		}

		const get_fabric_item_name = () => {
			if (doc.fabric_item) {
				frappe.db.get_value("Item", doc.fabric_item, "item_name", (r) => {
					if (r) {
						dialog.set_value("fabric_item_name", r.item_name);
					}
				});
			} else {
				dialog.set_value("fabric_item_name", null);
			}
		}

		const get_customer_name = () => {
			if (doc.customer) {
				frappe.db.get_value("Customer", doc.customer, "customer_name", (r) => {
					if (r) {
						dialog.set_value("customer_name", r.customer_name);
					}
				});
			} else {
				dialog.set_value("customer_name", null);
			}
		}

		const dialog = new frappe.ui.Dialog({
			title: __(title),
			fields: [
				{
					label: __("Fabric Item Code"),
					fieldname: "fabric_item",
					fieldtype: "Link",
					options: "Item",
					reqd: 1,
					get_query: () => erpnext.queries.item({
						textile_item_type: ["in", ["Ready Fabric", "Greige Fabric"]],
					}),
					onchange: () => {
						get_price();
						get_fabric_item_name();
					},
				},
				{
					label: __("Fabric Item Name"),
					fieldname: "fabric_item_name",
					depends_on: "eval:doc.fabric_item && doc.fabric_item_name != doc.fabric_item",
					fieldtype: "Data",
					read_only: 1,
				},
				{
					label: __("Customer"),
					fieldname: "customer",
					fieldtype: "Link",
					options: "Customer",
					onchange: () => {
						get_price();
						get_customer_name();
					},
				},
				{
					label: __("Customer Name"),
					fieldname: "customer_name",
					fieldtype: "Data",
					depends_on: "eval:doc.customer && doc.customer_name != doc.customer",
					read_only: 1,
				},
				{
					label: __("Price List"),
					fieldname: "price_list",
					fieldtype: "Link",
					options: "Price List",
					reqd: 1,
					get_query: () => {
						return {
							filters: {selling: 1}
						}
					},
					onchange: () => {
						get_price();
					},
				},
				{
					label: __("Rate"),
					fieldtype: "Section Break",
				},
				{
					label: __(base_rate_field_label),
					fieldname: base_rate_field_name,
					fieldtype: "Currency",
					read_only: 1,
				},
				{
					label: __(rate_field_label),
					fieldname: rate_field_name,
					fieldtype: "Currency",
					read_only: 1,
				},
				{
					label: __("Fabric Rate"),
					fieldname: "fabric_rate",
					fieldtype: "Currency",
					read_only: 1,
				},
				{
					label: __("Price List Rate"),
					fieldname: "price_list_rate",
					fieldtype: "Currency",
					read_only: 1,
					bold: 1
				},
				{
					fieldtype: "Section Break",
				},
				{
					label: __("Applied Rules"),
					fieldname: "applied_rules",
					fieldtype: "Table",
					read_only: 1,
					cannot_add_rows: 1,
					get_data: () => doc.applied_rules,
					fields: [
						{
							label: __("Rule"),
							fieldname: "rule",
							fieldtype: "Link",
							options: title === "Check Printing Rate" ? "Print Pricing Rule" : "Pretreatment Pricing Rule",
							read_only: 1,
							in_list_view: 1
						},
						{
							label: __("Type"),
							fieldname: "type",
							fieldtype: "Data",
							read_only: 1,
							in_list_view: 1
						},
						{
							label: __("Value"),
							fieldname: "value",
							fieldtype: "Float",
							read_only: 1,
							in_list_view: 1
						},
					]
				},
			],
			doc: doc,
		});
		dialog.show();
	});
}