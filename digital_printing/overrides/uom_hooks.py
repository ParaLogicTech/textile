import frappe
from frappe import _


def on_uom_conversion_factor_update(doc, method):
	from digital_printing.digital_printing.doctype.print_order.print_order import update_conversion_factor_global_defaults

	uoms = [doc.from_uom, doc.to_uom]
	if "Meter" in uoms or "Yard" in uoms or "Inch" in uoms:
		update_conversion_factor_global_defaults()


def before_uom_rename(doc, method, old, new, merge):
	if doc.name in ("Meter", "Yard", "Inch"):
		frappe.throw(_("Not allowed to rename UOM {0}").format(doc.name))
