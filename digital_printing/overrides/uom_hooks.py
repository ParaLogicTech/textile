import frappe
from frappe import _


def on_uom_conversion_factor_update(doc, method):
	uoms = [doc.from_uom, doc.to_uom]
	if "Meter" in uoms or "Yard" in uoms or "Inch" in uoms:
		update_conversion_factor_global_defaults()


def update_conversion_factor_global_defaults():
	from erpnext.setup.doctype.uom_conversion_factor.uom_conversion_factor import get_uom_conv_factor
	inch_to_meter = get_uom_conv_factor("Inch", "Meter")
	yard_to_meter = get_uom_conv_factor("Yard", "Meter")

	frappe.db.set_default("inch_to_meter", inch_to_meter)
	frappe.db.set_default("yard_to_meter", yard_to_meter)


def before_uom_rename(doc, method, old, new, merge):
	if doc.name in ("Meter", "Yard", "Inch"):
		frappe.throw(_("Not allowed to rename UOM {0}").format(doc.name))
