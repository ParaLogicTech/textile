frappe.ui.form.on('Item', {
	setup: function(frm) {
		frm.events.setup_custom_queries(frm);
	},

	refresh: function (frm) {
		frm.events.set_dynamic_fabric_item_label(frm);
	},

	setup_custom_queries(frm) {
		frm.set_query("fabric_item", function() {
			let filters = {
				textile_item_type: ["in", ["Ready Fabric", "Greige Fabric"]],
			};

			if (frm.doc.textile_item_type == "Printed Design") {
				filters.textile_item_type = "Ready Fabric";
			} else if (frm.doc.textile_item_type == "Ready Fabric") {
				filters.textile_item_type = "Greige Fabric";

				if (frm.doc.fabric_material) {
					filters.fabric_material = frm.doc.fabric_material;
				}
				if (frm.doc.fabric_type) {
					filters.fabric_type = frm.doc.fabric_type;
				}
			}

			return {
				filters: filters,
			}
		});
	},

	textile_item_type(frm) {
		frm.events.set_dynamic_fabric_item_label(frm);

		if (!["Ready Fabric", "Printed Design"].includes(frm.doc.textile_item_type) && frm.doc.fabric_item) {
			frm.set_value("fabric_item", null)
		}
	},

	fabric_item(frm) {
		if (frm.doc.textile_item_type == "Printed Design") {
			return frm.events.get_fabric_item_details(frm);
		}
	},

	get_fabric_item_details(frm) {
		return frappe.call({
			method: "textile.overrides.item_hooks.get_fabric_item_details",
			args: {
				fabric_item: frm.doc.fabric_item || "",
			},
			callback: (r) => {
				if (r.message) {
					frm.set_value(r.message);
				}
			}
		})
	},

	set_dynamic_fabric_item_label(frm) {
		let code_label = __("Fabric Item");
		let name_label = __("Fabric Item Name");

		if (frm.doc.textile_item_type == "Printed Design") {
			code_label = __("Ready Fabric Item");
			name_label = __("Ready Fabric Name");
		} else if (frm.doc.textile_item_type == "Ready Fabric") {
			code_label = __("Greige Fabric Item");
			name_label = __("Greige Fabric Name");
		}

		frm.set_df_property("fabric_item", "label", code_label);
		frm.set_df_property("fabric_item_name", "label", name_label);
	}
});
