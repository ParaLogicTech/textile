import frappe
from frappe import _
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class StockEntryDP(StockEntry):
	def validate(self):
		super().validate()
		self.validate_fabric_printer()
		self.validate_print_process()

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

	def validate_fabric_printer(self):
		if self.purpose != "Manufacture":
			return

		if self.get("print_order"):
			if not self.get("fabric_printer"):
				frappe.throw(_("Fabric Printer mandatory for Manufacture Stock Entry of Print Order"))
		else:
			self.fabric_printer = None

	def validate_print_process(self):
		if self.purpose != "Manufacture":
			return
		if not self.get("fabric_printer") or not self.get("work_order"):
			return

		printer_process = frappe.get_cached_value("Fabric Printer", self.fabric_printer, "process_item")
		work_order_process = frappe.db.get_value("Work Order", self.work_order, "process_item", cache=1)

		if printer_process and printer_process != work_order_process:
			frappe.throw(_("Fabric Printer {0} is not allowed to manufacture using Process {1} in {2}").format(
				self.fabric_printer, work_order_process, frappe.get_desk_link("Work Order", self.work_order)
			))


def update_stock_entry_from_work_order(stock_entry, work_order):
	stock_entry.pretreatment_order = work_order.pretreatment_order
	stock_entry.print_order = work_order.print_order
