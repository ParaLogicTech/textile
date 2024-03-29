import frappe
from frappe import _


def on_uom_conversion_factor_update(doc, method):
	from textile.utils import update_conversion_factor_global_defaults

	uoms = [doc.from_uom, doc.to_uom]
	if "Meter" in uoms or "Yard" in uoms or "Inch" in uoms:
		update_conversion_factor_global_defaults()


def before_uom_rename(doc, method, old, new, merge):
	if doc.name in ("Meter", "Yard", "Inch", "Square Meter"):
		frappe.throw(_("Not allowed to rename UOM {0}").format(doc.name))
