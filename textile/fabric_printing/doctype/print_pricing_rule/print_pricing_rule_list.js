frappe.listview_settings["Print Pricing Rule"] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Check Printing Rate"), () => {
			let doc = {
				price_list: frappe.defaults.get_global_default("selling_price_list")
			};

			const get_price = () => {
				if (doc.price_list && doc.fabric_item) {
					return frappe.call({
						method: "textile.overrides.item_details_hooks.get_design_item_price_breakup",
						args: {
							price_list: doc.price_list,
							item_code: doc.fabric_item,
							customer: doc.customer
						},
						callback: (r) => {
							if (r.message) {
								doc.base_printing_rate = r.message.base_printing_rate;
								doc.printing_rate = r.message.printing_rate;
								doc.fabric_rate = r.message.fabric_rate;
								doc.price_list_rate = r.message.price_list_rate;
								dialog.refresh();
							}
						}
					});
				} else {
					doc.base_printing_rate = null;
					doc.printing_rate = null;
					doc.fabric_rate = null;
					doc.price_list_rate = null;
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
				title: __("Check Printing Rate"),
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
						fieldtype: "Section Break",
					},
					{
						label: __("Base Printing Rate"),
						fieldname: "base_printing_rate",
						fieldtype: "Currency",
						read_only: 1,
					},
					{
						label: __("Printing Rate"),
						fieldname: "printing_rate",
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
				],
				doc: doc,
			});
			dialog.show();
		});
	}
};
