# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from textile.digital_printing.doctype.print_order.print_order import validate_print_item


class FabricPrinter(Document):
	def validate(self):
		if self.get("process_item"):
			validate_print_item(self.process_item, "Print Process")
