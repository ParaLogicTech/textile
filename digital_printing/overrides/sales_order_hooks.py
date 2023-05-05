import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder


class SalesOrderDP(SalesOrder):
	def update_previous_doc_status(self):
		super().update_previous_doc_status()

		print_orders = [d.print_order for d in self.items if d.get('print_order')]
		print_order_row_names = [d.print_order_item for d in self.items if d.get('print_order_item')]

		for name in print_orders:
			doc = frappe.get_doc("Print Order", name)
			doc.set_ordered_status(update=True)

			doc.validate_ordered_qty(from_doctype=self.doctype, row_names=print_order_row_names)

			doc.set_status(update=True)
			doc.notify_update()


def override_sales_order_dashboard(data):
	data["internal_links"]["Print Order"] = ["items", "print_order"]
	ref_section = [d for d in data["transactions"] if d["label"] == _("Reference")][0]
	ref_section["items"].insert(0, "Print Order")
	return data


def set_print_order_reference_in_work_order(work_order):
	if not work_order.get('sales_order_item'):
		return

	res = frappe.db.get_value("Sales Order Item", work_order.sales_order_item, ["print_order", "print_order_item"], as_dict=1)

	if res:
		work_order.print_order = res.print_order
		work_order.print_order_item = res.print_order_item


def set_print_order_warehouses_in_work_order(work_order):
	if not work_order.get('print_order'):
		return

	po_to_wo_warehouse_fn_map = {
		'source_warehouse': 'source_warehouse',
		'wip_warehouse': 'wip_warehouse',
		'fg_warehouse': 'fg_warehouse',
	}

	for po_warehouse_fn, wo_warehouse_fn in po_to_wo_warehouse_fn_map.items():
		warehouse = frappe.db.get_value("Print Order", work_order.print_order, po_warehouse_fn, cache=True)

		if warehouse:
			work_order.set(wo_warehouse_fn, warehouse)


def map_print_order_reference_in_target_item(mapper, target_doctype):
	if not mapper.get("Sales Order Item"):
		return

	field_map = mapper["Sales Order Item"]["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"
