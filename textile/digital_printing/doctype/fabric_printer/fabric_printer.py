# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from textile.utils import validate_textile_item


class FabricPrinter(Document):
	def validate(self):
		if self.get("process_item"):
			validate_textile_item(self.process_item, "Print Process")
