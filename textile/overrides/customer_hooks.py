# import frappe
from frappe import _
from textile.fabric_printing.doctype.print_order.print_order import validate_uom_and_qty_type


def customer_order_default_validate(self, hook):
	validate_uom_and_qty_type(self)


def override_customer_dashboard(data):
	data["transactions"].append({
		"label": _("Textile"),
		"items": ["Pretreatment Order", "Print Order"]
	})
	return data
