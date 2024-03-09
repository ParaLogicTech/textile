import frappe
# from frappe import _
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from textile.fabric_printing.doctype.print_order.print_order import validate_transaction_against_print_order
from textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order import validate_transaction_against_pretreatment_order
from textile.utils import is_row_return_fabric


class DeliveryNoteDP(DeliveryNote):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.force_item_fields += ["fabric_item", "fabric_item_name", "is_printed_fabric"]

	def set_missing_values(self, for_validate=False):
		super().set_missing_values(for_validate=for_validate)
		self.set_is_return_fabric()

	def set_is_return_fabric(self):
		for d in self.items:
			d.is_return_fabric = is_row_return_fabric(self, d)

	def validate_with_previous_doc(self):
		super().validate_with_previous_doc()
		validate_transaction_against_pretreatment_order(self)
		validate_transaction_against_print_order(self)

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		pretreatment_orders = set([d.pretreatment_order for d in self.items if d.get('pretreatment_order')])
		for name in pretreatment_orders:
			doc = frappe.get_doc("Pretreatment Order", name)
			doc.set_delivery_status(update=True)
			doc.validate_delivered_qty(from_doctype=self.doctype)

			# Update packed qty for unpacked returns
			if self.is_return and self.reopen_order:
				doc.set_production_packing_status(update=True)

			doc.set_status(update=True)
			doc.notify_update()

		print_orders = set([d.print_order for d in self.items if d.get('print_order')])
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]
		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_delivery_status(update=True)
			doc.validate_delivered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			# Update packed qty for unpacked returns
			if self.is_return and self.reopen_order:
				doc.set_production_packing_status(update=True)

			doc.set_status(update=True)
			doc.notify_update()

	def update_status(self, status):
		super().update_status(status)

		pretreatment_orders = set([d.pretreatment_order for d in self.items if d.get('pretreatment_order')])
		for name in pretreatment_orders:
			doc = frappe.get_doc("Pretreatment Order", name)
			doc.run_method("update_status", None)

		print_orders = set([d.print_order for d in self.items if d.get('print_order')])
		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.run_method("update_status", None)

	def get_skip_sales_invoice(self, row):
		is_return_fabric = is_row_return_fabric(self, row)
		if is_return_fabric:
			return True


def override_delivery_note_dashboard(data):
	from textile.utils import override_sales_transaction_dashboard
	return override_sales_transaction_dashboard(data)


def update_delivery_note_mapper(mapper, target_doctype):
	if not mapper.get("Delivery Note Item"):
		return

	field_map = mapper["Delivery Note Item"]["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"


def update_return_mapper(mapper, doctype):
	child_dt = f"{doctype} Item"
	if not mapper.get(child_dt):
		return

	field_map = mapper[child_dt]["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"

	if not frappe.flags.args or not frappe.flags.args.reopen_order:
		if not frappe.flags.args:
			frappe.flags.args = frappe._dict()

		frappe.flags.args.reopen_order = "Yes"
