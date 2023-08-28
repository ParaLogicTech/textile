frappe.listview_settings['Pretreatment Order'] = {
	add_fields: ["status"],

	get_indicator: function(doc) {
		if (doc.status === "Not Started") {
			return [__(doc.status), "yellow", "status,=," + doc.status];
		} else if(doc.status === "To Produce") {
			return [__(doc.status), "purple", "status,=," + doc.status];
		} else if(doc.status === "To Deliver") {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if(doc.status === "To Bill") {
			return [__(doc.status), "yellow", "status,=," + doc.status];
		} else if(["Completed", "Closed"].includes(doc.status)) {
			return [__(doc.status), "green", "status,=," + doc.status];
		}
	},

	onload: function(listview) {
		if (listview.page.fields_dict.greige_fabric_item) {
			listview.page.fields_dict.greige_fabric_item.get_query = () => {
				return erpnext.queries.item({"textile_item_type": "Greige Fabric", "include_disabled": 1});
			}
		}
		if (listview.page.fields_dict.ready_fabric_item) {
			listview.page.fields_dict.ready_fabric_item.get_query = () => {
				return erpnext.queries.item({"textile_item_type": "Ready Fabric", "include_disabled": 1});
			}
		}
	},
};
