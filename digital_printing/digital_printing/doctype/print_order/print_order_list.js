frappe.listview_settings['Print Order'] = {
	add_fields: ["status"],

	get_indicator: function(doc) {
		if(doc.status === "To Create Items") {
			return [__(doc.status), "yellow", "status,=," + doc.status];
		} else if(doc.status === "To Confirm Order") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Produce") {
			return [__(doc.status), "blue", "status,=," + doc.status];
		} else if(doc.status === "To Deliver") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Bill") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(["Completed", "Closed"].includes(doc.status)) {
			return [__(doc.status), "green", "status,=," + doc.status];
		}
	},

	onload: function(listview) {
		var method = "digital_printing.digital_printing.doctype.print_order.print_order.close_or_unclose_print_orders";

		listview.page.add_action_item(__("Close"), function() {
			listview.call_for_selected_items(method, {"status": "Closed"});
		});

		listview.page.add_action_item(__("Re-Open"), function() {
			listview.call_for_selected_items(method, {"status": "Submitted"});
		});
	}
};
