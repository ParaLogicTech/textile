import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


class StockEntryDP(StockEntry):
	def get_pro_order_required_items(self):
		item_dict = super().get_pro_order_required_items()

		if self.stock_entry_type == "Material Transfer for Manufacture" and self.work_order:
			if self.pro_doc.print_order and self.pro_doc.print_order_item:
				fabric_item = frappe.db.get_value("Print Order", self.pro_doc.print_order, "fabric_item", cache=1)
				length = frappe.db.get_value("Print Order Item", self.pro_doc.print_order_item,
					["stock_print_length", "stock_fabric_length"], as_dict=1)

				if fabric_item and length and length.stock_fabric_length:
					row = item_dict.get(fabric_item)
					if row:
						ratio = length.stock_fabric_length / length.stock_print_length
						required_qty_with_wastage = row.required_qty * ratio
						row.required_qty = required_qty_with_wastage
						row.no_allowance = True

		return item_dict
