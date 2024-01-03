# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FabricPretreatmentSettings(Document):
	def validate(self):
		self.update_global_defaults()

	def update_global_defaults(self):
		global_default_fields = [
			"default_pretreatment_fabric_warehouse",
			"default_pretreatment_source_warehouse",
			"default_pretreatment_wip_warehouse",
			"default_pretreatment_fg_warehouse",
			"default_pretreatment_cost_center",
		]

		for fn in global_default_fields:
			frappe.db.set_default(fn, self.get(fn, ''))
