# import frappe
from digital_printing.digital_printing.doctype.print_order.print_order import validate_uom_and_qty_type


def customer_order_default_validate(self, hook):
	validate_uom_and_qty_type(self)
