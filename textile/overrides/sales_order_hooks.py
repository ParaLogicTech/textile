import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from textile.fabric_printing.doctype.print_order.print_order import validate_transaction_against_print_order
from textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order import validate_transaction_against_pretreatment_order


class SalesOrderDP(SalesOrder):
	def validate_with_previous_doc(self):
		super(SalesOrderDP, self).validate_with_previous_doc()
		validate_transaction_against_pretreatment_order(self)
		validate_transaction_against_print_order(self)

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		pretreatment_orders = set([d.pretreatment_order for d in self.items if d.get('pretreatment_order')])
		for name in pretreatment_orders:
			doc = frappe.get_doc("Pretreatment Order", name)
			doc.set_sales_order_status(update=True)
			doc.set_production_packing_status(update=True)

			doc.validate_ordered_qty(from_doctype=self.doctype)

			doc.set_status(update=True)
			doc.notify_update()

		print_orders = []
		if not frappe.flags.skip_print_order_status_update:
			print_orders = set([d.print_order for d in self.items if d.get('print_order')])
			print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_sales_order_status(update=True)
			doc.set_production_packing_status(update=True)

			doc.validate_ordered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

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

	def get_sales_order_item_bom(self, row):
		if row.get('pretreatment_order'):
			return frappe.db.get_value("Pretreatment Order", row.pretreatment_order, "ready_fabric_bom", cache=1)
		if row.get('print_order_item'):
			return frappe.db.get_value("Print Order Item", row.print_order_item, "design_bom", cache=1)


def override_sales_order_dashboard(data):
	data["internal_links"]["Pretreatment Order"] = ["items", "pretreatment_order"]
	data["internal_links"]["Print Order"] = ["items", "print_order"]

	textile_section = {
		"label": _("Textile"),
		"items": ["Pretreatment Order", "Print Order"]
	}
	data["transactions"].append(textile_section)

	return data


def update_sales_order_mapper(mapper, target_doctype):
	if not mapper.get("Sales Order Item"):
		return

	field_map = mapper["Sales Order Item"]["field_map"]

	field_map["pretreatment_order"] = "pretreatment_order"

	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"
