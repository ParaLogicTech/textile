frappe.listview_settings['Coating Order'] = {
	add_fields: ["status"],

	get_indicator: function(doc) {
		if (doc.status === "Not Started") {
			return [__(doc.status), "yellow", "status,=," + doc.status];
		} else if(doc.status === "To Coat") {
			return [__(doc.status), "purple", "status,=," + doc.status];
		} else if(doc.status === "In Process") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(["Completed", "Closed"].includes(doc.status)) {
			return [__(doc.status), "green", "status,=," + doc.status];
		}
	},

	setup_defaults: function() {
		this.sort_by = "qty";
		this.sort_order = "desc";

		return out;
	}

};
