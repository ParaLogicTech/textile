import frappe
from frappe import _
from erpnext.stock.doctype.item.item import Item
from frappe.utils import cstr


class ItemDP(Item):
	def validate(self):
		super().validate()
		self.validate_print_item_type()
		self.validate_fabric_properties()
		self.validate_design_properties()

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

				if not self.design_name:
					frappe.throw(_("Design Name is mandatory for Printed Design Item"))
				if not self.fabric_item:
					frappe.throw(_("Fabric Item is mandatory for Printed Design Item"))
				if not self.process_item:
					frappe.throw(_("Print Process Item is mandatory for Printed Design Item"))

				if frappe.get_cached_value("Item", self.fabric_item, "print_item_type") != "Fabric":
					frappe.throw(_("Item {0} is not a Fabric Item").format(self.fabric_item))

				if frappe.get_cached_value("Item", self.process_item, "print_item_type") != "Print Process":
					frappe.throw(_("Item {0} is not a Print Process Item").format(self.process_item))

	def validate_fabric_properties(self):
		self.fabric_item = self.fabric_item if self.print_item_type == "Printed Design" else None

		if self.print_item_type == "Fabric":
			if not self.design_width:
				frappe.throw(_("Design Width is required."))

			if not self.fabric_material:
				frappe.throw(_("Fabric Material is required."))
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
			self.process_item = None
			self.design_notes = None
			self.fabric_item = None


def update_item_override_fields(item_fields, args, validate=False):
    item_fields['print_item_type'] = 'Data'
