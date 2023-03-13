frappe.listview_settings['Print Order'] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		if(doc.status === "To Create Items") {
			return [__(doc.status), "yellow", "status,=," + doc.status];
		} else if(doc.status === "To Receive Fabric") {
			return [__(doc.status), "purple", "status,=," + doc.status];
		} else if(doc.status === "To Confirm Order") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Order Production") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Finish Production") {
			return [__(doc.status), "blue", "status,=," + doc.status];
		} else if(doc.status === "To Deliver") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Bill") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "Completed") {
			return [__(doc.status), "green", "status,=," + doc.status];
		}
	},
};
