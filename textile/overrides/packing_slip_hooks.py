import frappe
from frappe import _
from erpnext.stock.doctype.packing_slip.packing_slip import PackingSlip
from textile.fabric_printing.doctype.print_order.print_order import validate_transaction_against_print_order
from textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order import validate_transaction_against_pretreatment_order
from textile.overrides.taxes_and_totals_hooks import calculate_panel_qty
from textile.utils import is_row_return_fabric


class PackingSlipDP(PackingSlip):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.force_item_fields += ["fabric_item", "fabric_item_name"]

	def set_missing_values(self, for_validate=False):
		super().set_missing_values(for_validate=for_validate)
		self.set_is_return_fabric()

	def set_is_return_fabric(self):
		for d in self.items:
			d.is_return_fabric = is_row_return_fabric(self, d)

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc()
		validate_transaction_against_print_order(self)
		validate_transaction_against_pretreatment_order(self)

	def set_default_package_type(self):
		print_orders = set([d.get("print_order") for d in self.get("items") if d.get("print_order")])
		pretreatment_orders = set([d.get("pretreatment_order") for d in self.get("items") if d.get("pretreatment_order")])

		if print_orders and not self.package_type:
			self.package_type = frappe.get_cached_value("Fabric Printing Settings", None,
				"default_package_type_for_printed_fabrics")
		if pretreatment_orders and not self.package_type:
			self.package_type = frappe.get_cached_value("Fabric Pretreatment Settings", None,
				"default_package_type_for_ready_fabrics")

	@frappe.whitelist()
	def add_return_fabric(self):
		self._add_return_fabric()
		self.run_method("set_missing_values")
		self.run_method("calculate_totals")

	def _add_return_fabric(self):
		print_orders = set([d.get("print_order") for d in self.get("items") if d.get("print_order")])
		pretreatment_orders = set([d.get("pretreatment_order") for d in self.get("items") if d.get("pretreatment_order")])

		for name in pretreatment_orders:
			order_details = frappe.db.get_value("Pretreatment Order", name,
				["greige_fabric_item", "greige_fabric_item_name", "uom", "wip_warehouse"], as_dict=1)

			if not self.has_return_fabric(order_details.greige_fabric_item):
				self.append('items', {
					"item_code": order_details.greige_fabric_item,
					"item_name": "{0} ({1})".format(order_details.greige_fabric_item_name, _("Return Fabric")),
					"qty": 0,
					"uom": order_details.uom,
					"source_warehouse": order_details.wip_warehouse,
					"pretreatment_order": name,
					"is_return_fabric": 1,
				})

		for name in print_orders:
			order_details = frappe.db.get_value("Print Order", name,
				["fabric_item", "fabric_item_name", "default_length_uom", "wip_warehouse"], as_dict=1)

			if not self.has_return_fabric(order_details.fabric_item):
				self.append('items', {
					"item_code": order_details.fabric_item,
					"item_name": "{0} ({1})".format(order_details.fabric_item_name, _("Return Fabric")),
					"qty": 0,
					"uom": order_details.default_length_uom,
					"source_warehouse": order_details.wip_warehouse,
					"print_order": name,
					"is_return_fabric": 1,
				})

	def has_return_fabric(self, fabric_item):
		return fabric_item in [d.item_code for d in self.get("items") if d.get("item_code") and d.get("is_return_fabric")]

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		pretreatment_orders = set([d.pretreatment_order for d in self.items if d.get('pretreatment_order')])
		for name in pretreatment_orders:
			doc = frappe.get_doc("Pretreatment Order", name)
			doc.set_production_packing_status(update=True)
			doc.validate_packed_qty(from_doctype=self.doctype)
			doc.set_status(update=True)
			doc.notify_update()

		print_orders = set([d.print_order for d in self.items if d.get('print_order')])
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]
		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_production_packing_status(update=True)
			doc.validate_packed_qty(from_doctype=self.doctype, row_names=print_order_row_names)
			doc.set_status(update=True)
			doc.notify_update()

	def calculate_totals(self):
		super().calculate_totals()
		calculate_panel_qty(self)


def update_packing_slip_mapper(item_mapper, source_doctype):
	if not item_mapper.get('field_map'):
		item_mapper['field_map'] = {}

	field_map = item_mapper["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def update_packing_slip_from_sales_order_mapper(mapper, target_doctype):
	def postprocess(source, target):
		target.set_default_package_type()
		target._add_return_fabric()

		if base_postprocess:
			base_postprocess(source, target)

	base_postprocess = mapper.get("postprocess")
	mapper["postprocess"] = postprocess


def override_packing_slip_dashboard(data):
	from textile.utils import override_sales_transaction_dashboard
	return override_sales_transaction_dashboard(data)
