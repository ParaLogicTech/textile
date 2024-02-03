# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt
import frappe
from frappe.utils import flt
from frappe.model.document import Document


class FabricMaterial(Document):
	def get_tariff_number(self, textile_item_type, fabric_gsm):
		fabric_gsm = flt(fabric_gsm)

		table_field = None
		if textile_item_type == "Greige Fabric":
			table_field = "greige_fabric_tariff"
		elif textile_item_type == "Ready Fabric":
			table_field = "ready_fabric_tariff"
		elif textile_item_type == "Printed Design":
			table_field = "printed_fabric_tariff"

		if not table_field:
			return None

		for d in self.get(table_field):
			if d.gsm_low and fabric_gsm < d.gsm_low:
				continue
			if d.gsm_high and fabric_gsm > d.gsm_high:
				continue

			return d.customs_tariff_number


def update_item_tariff_numbers(fabric_material):
	frappe.has_permission("Item", ptype="write", throw=True)

	material_doc = frappe.get_doc("Fabric Material", fabric_material)
	items = frappe.get_all("Item", filters={"fabric_material": fabric_material},
		fields=["name", "textile_item_type", "fabric_gsm"])

	for d in items:
		tariff_number = material_doc.get_tariff_number(d.textile_item_type, d.fabric_gsm)
		if tariff_number:
			frappe.db.set_value("Item", d.name, "customs_tariff_number", tariff_number, update_modified=False)
