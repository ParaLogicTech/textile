import frappe
from frappe import _
from frappe.utils import flt
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder, StockOverProductionError


class WorkOrderDP(WorkOrder):
	def validate_overproduction(self):
		if self.get("print_order") and self.get("print_order_item"):
			transferred_qty = flt(self.material_transferred_for_manufacturing, self.precision("qty"))
			stock_fabric_length = flt(frappe.db.get_value("Print Order Item", self.print_order_item, "stock_fabric_length"),
				self.precision("qty"))

			if transferred_qty > stock_fabric_length:
				frappe.throw(_("Cannot transfer more than Fabric Length {0} Meter for Print Order {1}").format(
					frappe.bold(frappe.format(stock_fabric_length)), self.print_order
				), StockOverProductionError)

		super().validate_overproduction()


def update_print_order_status(self, hook, status=None):
	if not (self.get('print_order') and self.get('print_order_item')):
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
