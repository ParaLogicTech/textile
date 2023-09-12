// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("textile");

textile.PretreatmentProcessRule = class PretreatmentProcessRule extends frappe.ui.form.Controller {
	setup() {
		this.setup_queries();
	}

	setup_queries() {
		for (let [component_item_field, component_type] of Object.entries(textile.pretreatment_components)) {
			this.frm.set_query(component_item_field, () => {
				return erpnext.queries.item({
					textile_item_type: 'Process Component',
					process_component: component_type
				});
			});
		}
	}
}

extend_cscript(cur_frm.cscript, new textile.PretreatmentProcessRule({frm: cur_frm}));
