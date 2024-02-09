frappe.listview_settings["Pretreatment Pricing Rule"] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Check Pretreatment Rate"), () => {
			let doc = {
				price_list: frappe.defaults.get_global_default("selling_price_list"),
				applied_rules: [],
			};

			const get_price = () => {
				if (doc.price_list && doc.fabric_item) {
					return frappe.call({
						method: "textile.fabric_pretreatment.doctype.pretreatment_pricing_rule.pretreatment_pricing_rule.get_pretreatment_rate_breakup",
						args: {
							item_code: doc.fabric_item,
							price_list: doc.price_list,
							customer: doc.customer
						},
						callback: (r) => {
							if (r.message) {
								doc.base_pretreatment_rate = r.message.base_rate;
								doc.pretreatment_rate = r.message.rule_rate;
								doc.fabric_rate = r.message.fabric_rate;
								doc.price_list_rate = r.message.price_list_rate;
								doc.applied_rules = r.message.applied_rules || [];
								dialog.refresh();
							}
						}
					});
				} else {
					doc.base_pretreatment_rate = null;
					doc.pretreatment_rate = null;
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
				title: __("Check Pretreatment Rate"),
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
						label: __("Base Pretreatment Rate"),
						fieldname: "base_pretreatment_rate",
						fieldtype: "Currency",
						read_only: 1,
					},
					{
						label: __("Pretreatment Rate"),
						fieldname: "pretreatment_rate",
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
								options: "Pretreatment Pricing Rule",
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
};
