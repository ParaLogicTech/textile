import frappe
from frappe import _
from frappe.utils import flt
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


class WorkOrderDP(WorkOrder):
	def set_required_items(self, reset_only_qty=False):
		super().set_required_items(reset_only_qty)

		if not reset_only_qty and self.get("print_order"):
			fabric_item = frappe.db.get_value("Print Order", self.print_order, "fabric_item", cache=1)
			for d in self.get("required_items"):
				if d.item_code == fabric_item:
					d.source_warehouse = self.wip_warehouse


def update_work_order_from_sales_order(work_order):
	if work_order.get('sales_order_item'):
		so_item = frappe.db.get_value("Sales Order Item", work_order.sales_order_item, ["print_order", "print_order_item"],
			as_dict=1)

		if so_item:
			work_order.print_order = so_item.print_order
			work_order.print_order_item = so_item.print_order_item

	if work_order.get('print_order'):
		work_order.skip_transfer = 1
		work_order.from_wip_warehouse = 0

		po_to_wo_warehouse_fn_map = {
			'source_warehouse': 'source_warehouse',
			'wip_warehouse': 'wip_warehouse',
			'fg_warehouse': 'fg_warehouse',
		}

		for po_warehouse_fn, wo_warehouse_fn in po_to_wo_warehouse_fn_map.items():
			warehouse = frappe.db.get_value("Print Order", work_order.print_order, po_warehouse_fn, cache=True)

			if warehouse:
				work_order.set(wo_warehouse_fn, warehouse)

	if work_order.get('print_order_item'):
		work_order.max_qty = flt(frappe.db.get_value("Print Order Item", work_order.print_order_item, "stock_fabric_length"))


def update_print_order_status(self, hook, status=None):
	if not (self.get('print_order') and self.get('print_order_item')):
		return

	if frappe.flags.skip_print_order_status_update:
		return

	doc = frappe.get_doc("Print Order", self.print_order)

	if hook == 'update_status':
		doc.set_production_status(update=True)
		doc.validate_produced_qty(from_doctype=self.doctype, row_names=[self.print_order_item])
	else:
		doc.set_work_order_status(update=True)
		doc.validate_work_order_qty(from_doctype=self.doctype, row_names=[self.print_order_item])

	doc.set_status(update=True)
	doc.notify_update()
