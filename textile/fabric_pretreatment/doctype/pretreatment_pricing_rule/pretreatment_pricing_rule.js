// Copyright (c) 2024, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Pretreatment Pricing Rule', {
	setup: function(frm) {
		frm.set_query("price_list", () => {
			return {
				filters: {
					selling: 1
				}
			}
		})
	}
});
