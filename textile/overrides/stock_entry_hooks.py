import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class StockEntryDP(StockEntry):
	def on_submit(self):
		super().on_submit()
		self.update_print_order_fabric_transfer_status()

	def on_cancel(self):
		super().on_cancel()
		self.update_print_order_fabric_transfer_status()

	def update_print_order_fabric_transfer_status(self):
		if not self.get("print_order"):
			return
		if self.purpose not in ("Material Transfer", "Material Transfer for Manufacture"):
			return
		if self.get("work_order"):
			return

		if not frappe.flags.skip_print_order_status_update:
			print_order = frappe.get_doc("Print Order", self.print_order)
			print_order.set_fabric_transfer_status(update=True)
			print_order.notify_update()


def update_stock_entry_from_work_order(stock_entry, work_order):
	stock_entry.print_order = work_order.print_order
