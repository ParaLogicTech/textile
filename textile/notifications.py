def get_notification_config():
	return {
		"for_doctype": {
			"Print Order": {
				"status": ("not in", ("Completed", "Closed")),
				"docstatus": ("<", 2)
			},
		},
	}
