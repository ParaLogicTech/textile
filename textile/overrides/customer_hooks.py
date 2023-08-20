# import frappe
from frappe import _
from textile.fabric_printing.doctype.print_order.print_order import validate_uom_and_qty_type


def customer_order_default_validate(self, hook):
	validate_uom_and_qty_type(self)


def override_customer_dashboard(data):
	ref_section = [d for d in data["transactions"] if d["label"] == _("Pre Sales")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
