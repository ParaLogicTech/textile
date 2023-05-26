import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class StockEntryDP(StockEntry):
	def get_pro_order_required_items(self):
		item_dict = super().get_pro_order_required_items()

		if self.stock_entry_type == "Material Transfer for Manufacture" and self.work_order:
			print_order = frappe.db.get_value("Work Order", self.work_order, "print_order")
			if print_order:
				print_order_fields = ['fabric_item', 'total_fabric_length', 'total_print_length']
				print_order_details = frappe.get_value("Print Order", print_order, print_order_fields, as_dict=1)
				if print_order_details.fabric_item and print_order_details.total_print_length:
					row = item_dict.get(print_order_details.fabric_item)
					if row:
						ratio = print_order_details.total_fabric_length / print_order_details.total_print_length
						row.required_qty = row.required_qty * ratio

		return item_dict
