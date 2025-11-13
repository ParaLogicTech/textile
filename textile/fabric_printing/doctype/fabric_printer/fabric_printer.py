# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from textile.utils import validate_textile_item


class FabricPrinter(Document):
	def validate(self):
		self.validate_process_items()

	def validate_process_items(self):
		visited = set()
		for d in self.process_items:
			if d.process_item in visited:
				frappe.throw(_("Row #{0}: Duplicated Process Item {1}").format(
					d.idx, frappe.bold(d.process_item)
				))

			validate_textile_item(d.process_item, "Print Process")
			visited.add(d.process_item)
