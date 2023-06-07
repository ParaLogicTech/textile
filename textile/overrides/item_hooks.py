import frappe
from frappe import _
from erpnext.stock.doctype.item.item import Item
from frappe.utils import flt


class ItemDP(Item):
	def before_validate(self):
		self.calculate_net_weight_per_unit()
		self.validate_fabric_uoms()

	def validate(self):
		super().validate()
		self.validate_print_item_type()
		self.validate_fabric_properties()
		self.validate_design_properties()
		self.validate_process_properties()

	def validate_print_item_type(self):
		match self.print_item_type:
			case "Fabric":
				if not self.is_stock_item:
					frappe.throw(_("Fabric Item must be a Stock Item"))

			case "Print Process":
				if self.is_stock_item:
					frappe.throw(_("Print Process Item cannot be a Stock Item"))
				if self.is_fixed_asset:
					frappe.throw(_("Print Process Item cannot be a Fixed Asset"))

			case "Printed Design":
				if not self.is_stock_item:
					frappe.throw(_("Printed Design Item must be a Stock Item"))
				if not self.is_sales_item:
					frappe.throw(_("Printed Design Item must be a Sales Item"))

				if not self.design_name:
					frappe.throw(_("Design Name is mandatory for Printed Design Item"))
				if not self.fabric_item:
					frappe.throw(_("Fabric Item is mandatory for Printed Design Item"))

				if frappe.get_cached_value("Item", self.fabric_item, "print_item_type") != "Fabric":
					frappe.throw(_("Item {0} is not a Fabric Item").format(self.fabric_item))

			case "Process Component":
				if not self.print_process_component:
					frappe.throw(_("Print Process Component is mandatory for Process Component Item"))

	def validate_fabric_properties(self):
		self.fabric_item = self.fabric_item if self.print_item_type == "Printed Design" else None

		if self.print_item_type == "Fabric":
			if not self.fabric_width:
				frappe.throw(_("Fabric Width is required for Fabric Item."))

			if not self.fabric_material:
				frappe.throw(_("Fabric Material is required for Fabric Item."))

		else:
			if self.fabric_item:
				fabric_doc = frappe.get_cached_doc("Item", self.fabric_item)
			else:
				fabric_doc = frappe._dict()

			self.fabric_material = fabric_doc.fabric_material
			self.fabric_type = fabric_doc.fabric_type
			self.fabric_width = fabric_doc.fabric_width
			self.fabric_gsm = fabric_doc.fabric_gsm
			self.fabric_construction = fabric_doc.fabric_construction

	def validate_design_properties(self):
		if self.print_item_type != "Printed Design":
			self.design_name = None
			self.design_width = None
			self.design_height = None
			self.design_uom = None
			self.design_gap = None
			self.per_wastage = None
			self.design_notes = None
			self.fabric_item = None

	def validate_process_properties(self):
		from textile.digital_printing.doctype.print_process_rule.print_process_rule import print_process_components
		if self.print_item_type != "Print Process":
			for component_item_field in print_process_components:
				self.set(f"{component_item_field}_required", 0)

		if self.print_item_type != "Process Component":
			self.print_process_component = None

		if self.print_process_component not in ("Sublimation Paper", "Protection Paper"):
			self.paper_width = None
			self.paper_gsm = None

	def validate_fabric_uoms(self):
		from textile.digital_printing.doctype.print_order.print_order import get_yard_to_meter

		if self.print_item_type not in ["Fabric", "Printed Design"]:
			return

		if self.stock_uom != "Meter":
			frappe.throw(_("Default Unit of Measure must be Meter"))

		uoms = []

		for d in self.uom_conversion_graph:
			uoms += [d.from_uom, d.to_uom]

		if 'Yard' not in uoms:
			self.append("uom_conversion_graph", {
				"from_uom": "Yard",
				"from_qty": flt(1/get_yard_to_meter(), self.precision("conversion_factor", "uoms")),
				"to_uom": "Meter",
				"to_qty": 1
			})

		sq_meter_row = [d for d in self.uom_conversion_graph if
			(d.from_uom == "Square Meter" and d.to_uom == "Meter") or (d.from_uom == "Meter" and d.to_uom == "Square Meter")]
		sq_meter_row = sq_meter_row[0] if sq_meter_row else self.append("uom_conversion_graph")

		sq_meter_row.update({
			"from_qty": 1,
			"from_uom": "Meter",
			"to_qty": self.fabric_width * 0.0254,
			"to_uom": "Square Meter",
		})

	def calculate_net_weight_per_unit(self):
		if flt(self.fabric_gsm) and self.print_item_type in ["Fabric", "Printed Design"]:
			self.net_weight_per_unit = flt(self.fabric_gsm) * flt(self.fabric_width) * 0.0254
			self.net_weight_per_unit = flt(self.net_weight_per_unit, self.precision("net_weight_per_unit"))

			self.gross_weight_per_unit = 0
			self.weight_uom = "Gram"


def update_item_override_fields(item_fields, args, validate=False):
	item_fields['print_item_type'] = 'Data'


def override_item_dashboard(data):
	data.setdefault("non_standard_fieldnames", {})["Print Order"] = "fabric_item"

	ref_section = [d for d in data["transactions"] if d["label"] == _("Manufacture")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
