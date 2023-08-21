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
		self.validate_textile_item_type()
		self.validate_fabric_properties()
		self.validate_design_properties()
		self.validate_process_properties()

	def on_trash(self):
		super().on_trash()

		print_orders = frappe.db.sql_list("""
			select distinct parent
			from `tabPrint Order Item`
			where item_code = %s
		""", self.name)

		if not print_orders:
			return

		frappe.db.sql("""
			update `tabPrint Order Item`
			set item_code = null
			where item_code = %s
		""", self.name)

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_item_creation_status(update=True)
			doc.notify_update()

	def validate_textile_item_type(self):
		if self.textile_item_type in ("Ready Fabric", "Greige Fabric", "Printed Design"):
			if not self.is_stock_item:
				frappe.throw(_("Fabric Item must be a Stock Item"))

		if self.textile_item_type == "Ready Fabric":
			greige_fabric_details = frappe.get_cached_value("Item", self.fabric_item,
				["textile_item_type", "fabric_material", "fabric_type"], as_dict=1)

			if self.fabric_item and greige_fabric_details.textile_item_type != "Greige Fabric":
				frappe.throw(_("Item {0} is not a Greige Fabric Item").format(self.fabric_item))

			if self.fabric_material and self.fabric_material != greige_fabric_details.fabric_material:
				frappe.throw(_("Fabric Material does not match with Greige Fabric Item's Fabric Material {0}").format(
					frappe.bold(greige_fabric_details.fabric_material)
				))
			if self.fabric_type and self.fabric_type != greige_fabric_details.fabric_type:
				frappe.throw(_("Fabric Type does not match with Greige Fabric Item's Fabric Type {0}").format(
					frappe.bold(greige_fabric_details.fabric_material)
				))

		if self.textile_item_type == "Printed Design":
			if not self.fabric_item:
				frappe.throw(_("Ready Fabric Item is mandatory for Printed Design Item"))
			if frappe.get_cached_value("Item", self.fabric_item, "textile_item_type") != "Ready Fabric":
				frappe.throw(_("Item {0} is not a Ready Fabric Item").format(self.fabric_item))

		elif self.textile_item_type == "Print Process":
			if self.is_stock_item:
				frappe.throw(_("Print Process Item must not be a Stock Item"))
			if self.is_fixed_asset:
				frappe.throw(_("Print Process Item must not be a Fixed Asset"))

		elif self.textile_item_type == "Process Component":
			if not self.print_process_component:
				frappe.throw(_("Print Process Component is mandatory for Process Component Item"))

	def validate_fabric_properties(self):
		if self.textile_item_type not in ("Printed Design", "Ready Fabric"):
			self.fabric_item = None

		if self.textile_item_type in ("Ready Fabric", "Greige Fabric"):
			if not self.fabric_width:
				frappe.throw(_("Fabric Width is required for Fabric Item."))
			if not self.fabric_material:
				frappe.throw(_("Fabric Material is required for Fabric Item."))
		else:
			self.update(get_fabric_item_details(self.fabric_item))

	def validate_design_properties(self):
		if self.textile_item_type != "Printed Design":
			self.design_width = None
			self.design_height = None
			self.design_uom = None
			self.design_gap = None
			self.per_wastage = None
			self.design_notes = None

	def validate_process_properties(self):
		from textile.fabric_printing.doctype.print_process_rule.print_process_rule import print_process_components
		if self.textile_item_type != "Print Process":
			for component_item_field in print_process_components:
				self.set(f"{component_item_field}_required", 0)

		if self.textile_item_type != "Process Component":
			self.print_process_component = None

		if self.print_process_component not in ("Sublimation Paper", "Protection Paper"):
			self.paper_width = None
			self.paper_gsm = None

	def validate_fabric_uoms(self):
		from textile.fabric_printing.doctype.print_order.print_order import get_yard_to_meter

		if self.textile_item_type not in ["Ready Fabric", "Greige Fabric", "Printed Design"]:
			return

		if self.stock_uom != "Meter":
			frappe.throw(_("Default Unit of Measure must be Meter"))

		uoms = []

		for d in self.uom_conversion_graph:
			uoms += [d.from_uom, d.to_uom]

		if 'Yard' not in uoms:
			self.append("uom_conversion_graph", {
				"from_uom": "Yard",
				"from_qty": 1,
				"to_uom": "Meter",
				"to_qty": get_yard_to_meter()
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
		if flt(self.fabric_gsm) and self.textile_item_type in ["Ready Fabric", "Greige Fabric", "Printed Design"]:
			self.net_weight_per_unit = flt(self.fabric_gsm) * flt(self.fabric_width) * 0.0254
			self.net_weight_per_unit = flt(self.net_weight_per_unit, self.precision("net_weight_per_unit"))

			self.gross_weight_per_unit = 0
			self.weight_uom = "Gram"


def update_item_override_fields(item_fields, args, validate=False):
	item_fields['textile_item_type'] = 'Data'


def override_item_dashboard(data):
	data.setdefault("non_standard_fieldnames", {})["Print Order"] = "fabric_item"

	ref_section = [d for d in data["transactions"] if d["label"] == _("Manufacture")][0]
	ref_section["items"].insert(0, "Print Order")
	return data


@frappe.whitelist()
def get_fabric_item_details(fabric_item):
	out = frappe._dict()

	fabric_doc = frappe.get_cached_doc("Item", fabric_item) if fabric_item else frappe._dict()
	out.fabric_material = fabric_doc.fabric_material
	out.fabric_type = fabric_doc.fabric_type
	out.fabric_width = fabric_doc.fabric_width
	out.fabric_gsm = fabric_doc.fabric_gsm
	out.fabric_construction = fabric_doc.fabric_construction

	return out
