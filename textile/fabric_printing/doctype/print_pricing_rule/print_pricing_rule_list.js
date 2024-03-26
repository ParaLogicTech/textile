frappe.provide("textile");

frappe.listview_settings["Print Pricing Rule"] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Check Printing Rate"), () => {
			textile.print_pricing_dialog();
		});
	}
};
