# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FabricPrintingSettings(Document):
	def validate(self):
		self.update_global_defaults()

	def update_global_defaults(self):
		global_default_fields = [
			"default_printing_fabric_warehouse",
			"default_printing_source_warehouse",
			"default_printing_wip_warehouse",
			"default_printing_fg_warehouse",
			"default_coating_fg_warehouse",
			"default_printing_cost_center",
		]

		for fn in global_default_fields:
			frappe.db.set_default(fn, self.get(fn, ''))
