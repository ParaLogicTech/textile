// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.provide("textile");

textile.PrintProcessRule = class PrintProcessRule extends frappe.ui.form.Controller {
	setup() {
		this.setup_queries();
	}

	setup_queries() {
		this.frm.set_query("process_item", () => {
			return erpnext.queries.item({ textile_item_type: 'Print Process' });
		});

		for (let [component_item_field, component_type] of Object.entries(textile.printing_components)) {
			this.frm.set_query(component_item_field, () => {
				return erpnext.queries.item({
					textile_item_type: 'Process Component',
					process_component: component_type
				});
			});
		}
	}
}

extend_cscript(cur_frm.cscript, new textile.PrintProcessRule({frm: cur_frm}));
