import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from textile.digital_printing.doctype.print_order.print_order import check_print_order_is_closed


class SalesOrderDP(SalesOrder):
	def validate(self):
		super().validate()
		check_print_order_is_closed(self)

	def validate_with_previous_doc(self):
		super(SalesOrderDP, self).validate_with_previous_doc()

		super(SalesOrder, self).validate_with_previous_doc({
			"Print Order": {
				"ref_dn_field": "print_order",
				"compare_fields": [["customer", "="], ["company", "="]]
			},
			"Print Order Item": {
				"ref_dn_field": "print_order_item",
				"compare_fields": [["item_code", "="]],
				"is_child_table": True,
				"allow_duplicate_prev_row_id": True
			},
		})

	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_sales_order_status(update=True)

			doc.validate_ordered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()

	def update_status(self, status):
		super().update_status(status)

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.run_method("update_status", None)

	def get_sales_order_item_bom(self, row):
		if row.get('print_order_item'):
			return frappe.db.get_value("Print Order Item", row.print_order_item, "design_bom", cache=1)


def override_sales_order_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(0, "Print Order")
	return data


def map_print_order_reference_in_target_item(mapper, target_doctype):
	if not mapper.get("Sales Order Item"):
		return

	field_map = mapper["Sales Order Item"]["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"
