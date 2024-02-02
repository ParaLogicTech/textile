import frappe
from frappe.utils import cint, flt


def calculate_taxes_and_totals(self):
	calculate_panel_qty(self.doc)
	set_printed_fabric_details(self.doc)


def calculate_panel_qty(self):
	item_meta = frappe.get_meta(self.doctype + " Item")

	if not (
		item_meta.has_field('panel_length_meter') and
		item_meta.has_field('panel_based_qty') and
		item_meta.has_field('panel_qty')
	):
		return

	for row in self.items:
		if cint(row.panel_based_qty) and flt(row.panel_length_meter):
			row.panel_qty = flt(flt(row.stock_qty) / flt(row.panel_length_meter), row.precision("panel_qty"))
		else:
			row.panel_qty = 0


def set_printed_fabric_details(self):
	if not self.meta.has_field("printed_fabrics"):
		return

	# Group fabrics and calculate totals
	fabric_summary = {}
	for item in self.items:
		if not item.fabric_item or not item.is_printed_fabric:
			continue

		fabric_dict = fabric_summary.setdefault(item.fabric_item, frappe._dict({
			"fabric_item": item.fabric_item,
			"fabric_item_name": item.fabric_item_name,
			"fabric_qty": 0,
			"fabric_rate": 0,
			"fabric_amount": 0,
		}))

		fabric_dict.fabric_qty += flt(item.stock_qty)
		fabric_dict.fabric_amount += flt(item.amount)

	# Calculate Rate
	for fabric_dict in fabric_summary.values():
		fabric_dict.fabric_rate = fabric_dict.fabric_amount / fabric_dict.fabric_qty if fabric_dict.fabric_qty else 0

	# Update rows
	def get_row(fabric_item):
		existing_rows = [d for d in self.printed_fabrics if d.fabric_item == fabric_item]
		return existing_rows[0] if existing_rows else None

	rows = []
	for i, fabric_dict in enumerate(fabric_summary.values()):
		row = get_row(fabric_dict.fabric_item)
		if not row:
			row = self.append("printed_fabrics")

		row.idx = i + 1
		row.update(fabric_dict)

		rows.append(row)

	self.printed_fabrics = rows
