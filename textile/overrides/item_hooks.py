import frappe
from frappe import _
from erpnext.stock.doctype.item.item import Item
from frappe.utils import flt
from textile.utils import gsm_to_grams, get_fabric_item_details, get_yard_to_meter, printing_components


class ItemDP(Item):
	def before_insert(self):
		super().before_insert()
		self.validate_fabric_properties()

	def before_validate(self):
		self.validate_textile_item_type()
		self.validate_fabric_properties()
		self.set_design_details_from_image()
		self.validate_design_properties()
		self.validate_process_properties()
		self.calculate_net_weight_per_unit()
		self.validate_fabric_uoms()

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
			if self.fabric_item:
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
			if not self.process_component:
				frappe.throw(_("Process Component is mandatory for Process Component Item"))

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

	def set_design_details_from_image(self):
		# Print order will set the design dimensions, do not load image again for performance
		if self.flags.from_print_order:
			return

		# Not a printed design no need for design dimensions
		if self.textile_item_type != "Printed Design":
			self.design_width = None
			self.design_height = None
			return

		# Image removed? Lets not change the dimensions yet
		if not self.image:
			return

		# Dimensions not set but image is there
		if not self.design_width or not self.design_height:
			return self.set_design_dimensions()

		# Image changed
		if self.is_new() or self.image != self.db_get("image"):
			return self.set_design_dimensions()

	def set_design_dimensions(self):
		from textile.fabric_printing.doctype.print_order.print_order import get_image_details

		if self.image:
			design_details = get_image_details(self.image)
			self.design_width = design_details.design_width
			self.design_height = design_details.design_height
		else:
			self.design_width = None
			self.design_height = None

	def validate_process_properties(self):
		if self.textile_item_type != "Print Process":
			for component_item_field in printing_components:
				self.set(f"{component_item_field}_required", 0)

		if self.textile_item_type != "Process Component":
			self.process_component = None
			self.consumption_by_fabric_weight = 0

		if self.process_component not in ("Sublimation Paper", "Protection Paper"):
			self.paper_width = None
			self.paper_gsm = None

	def validate_fabric_uoms(self):
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
			self.net_weight_per_unit = gsm_to_grams(self.fabric_gsm, self.fabric_width)
			self.net_weight_per_unit = flt(self.net_weight_per_unit, self.precision("net_weight_per_unit"))

			self.gross_weight_per_unit = 0
			self.weight_uom = "Gram"

	_printed_design_cant_change_fields = [
		"fabric_item", "design_width", "design_height", "image", "is_customer_provided_item", "customer"
	]

	def get_cant_change_fields_based_on_transactions(self):
		return super().get_cant_change_fields_based_on_transactions() + ["textile_item_type"]

	def get_cant_change_fields(self):
		fields = super().get_cant_change_fields()

		if self.textile_item_type == "Printed Design":
			fields += self._printed_design_cant_change_fields

		return fields

	def check_if_cant_change_field(self, field):
		if super().check_if_cant_change_field(field):
			return True

		if field in self._printed_design_cant_change_fields:
			if self.check_if_linked_doctype_exists("Print Order Item"):
				return True

		if field in self.get_cant_change_fields_based_on_transactions():
			if self.check_if_linked_doctype_exists("Print Order Item"):
				return True

			if self.textile_item_type in ("Ready Fabric", "Greige Fabric"):
				fieldname = "ready_fabric_item" if self.textile_item_type == "Ready Fabric" else "greige_fabric_item"
				if self.check_if_linked_doctype_exists("Pretreatment Order", fieldname=fieldname):
					return True


def update_item_override_fields(item_fields, args, validate=False):
	item_fields['textile_item_type'] = 'Data'


def override_item_dashboard(data):
	data.setdefault("non_standard_fieldnames", {})["Print Order"] = "item_code"

	ref_section = [d for d in data["transactions"] if d["label"] == _("Manufacture")][0]
	ref_section["items"].insert(0, "Print Order")
	return data
