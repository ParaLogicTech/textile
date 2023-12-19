frappe.listview_settings['Coating Order'] = {
	add_fields: ["status"],

	get_indicator: function(doc) {
		return [__(doc.status), {
			"Not Started": "yellow",
			"In Process": "orange",
			"Stopped": "green",
			"Completed": "green",
		}[doc.status], "status,=," + doc.status];
	},
};
