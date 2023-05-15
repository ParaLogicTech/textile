import frappe
from frappe.utils import flt


def calculate_panel_qty(self):
	item_meta = frappe.get_meta(self.doc.doctype + " Item")

	if not item_meta.has_field('panel_length_meter') or not item_meta.has_field('panel_qty'):
		return

	for row in self.doc.items:
		if row.panel_length_meter:
			row.panel_qty = flt(row.stock_qty / row.panel_length_meter, row.precision("panel_qty"))
		else:
			row.panel_qty = 0
