frappe.listview_settings['Work Order'].original_onload = frappe.listview_settings['Work Order'].onload;
frappe.listview_settings['Work Order'].onload = function(listview) {
	frappe.listview_settings['Work Order'].original_onload(listview);

	if (listview.page.fields_dict.fabric_item) {
		listview.page.fields_dict.fabric_item.get_query = () => {
			return erpnext.queries.item({
				"textile_item_type": ["in", ["Ready Fabric", "Greige Fabric"]],
				"include_disabled": 1
			});
		}
	}

	if (listview.page.fields_dict.process_item) {
		listview.page.fields_dict.process_item.get_query = () => {
			return erpnext.queries.item({"textile_item_type": "Print Process", "include_disabled": 1});
		}
	}
}
