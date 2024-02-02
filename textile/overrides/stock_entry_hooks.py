import frappe
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.get_item_details import get_conversion_factor


class StockEntryDP(StockEntry):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.force_item_fields += ["fabric_item", "fabric_item_name"]

	def validate(self):
		super().validate()
		self.validate_fabric_printer()
		self.validate_print_process()

	def on_submit(self):
		super().on_submit()
		self.update_print_order_fabric_transfer_status()
		self.update_coating_order(validate_coating_order_qty=True)

	def on_cancel(self):
		super().on_cancel()
		self.update_print_order_fabric_transfer_status()
		self.update_coating_order()

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

	def update_coating_order(self, validate_coating_order_qty=False):
		if not self.coating_order:
			return

		coating_order_doc = frappe.get_doc("Coating Order", self.coating_order)

		if coating_order_doc.docstatus != 1:
			frappe.throw(_("Coating Order {0} must be submitted").format(self.coating_order))

		if coating_order_doc.status == 'Stopped':
			frappe.throw(_("Transaction not allowed against stopped Coating Order {0}").format(self.coating_order))

		coating_order_doc.set_coating_status(update=True)

		if validate_coating_order_qty:
			coating_order_doc.validate_coating_order_qty(from_doctype=self.doctype)

		coating_order_doc.set_status(update=True)
		coating_order_doc.notify_update()

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

	def get_bom_raw_materials(self, qty, scrap_qty=0):
		from textile.utils import gsm_to_grams

		if self.coating_order:
			coating_order_doc = frappe.get_doc("Coating Order", self.coating_order)

			if coating_order_doc.coating_item_by_fabric_weight:
				fabric_grams_per_meter = gsm_to_grams(coating_order_doc.fabric_gsm, coating_order_doc.fabric_width)
				consumption_grams_per_meter = fabric_grams_per_meter * flt(coating_order_doc.fabric_per_pickup) / 100
				cf_coating = get_conversion_factor(coating_order_doc.coating_item, "Gram").conversion_factor * consumption_grams_per_meter

			else:
				cf_coating = get_conversion_factor(coating_order_doc.coating_item, coating_order_doc.stock_uom).conversion_factor

			coating_item_qty = qty * cf_coating
			item_dict = super().get_bom_raw_materials(coating_item_qty, scrap_qty)
			item_dict = {
				coating_order_doc.fabric_item: {
					'item_code': coating_order_doc.fabric_item,
					'from_warehouse': coating_order_doc.fabric_warehouse,
					'uom': coating_order_doc.stock_uom,
					'qty': qty,
				}, **item_dict
			}

		else:
			item_dict = super().get_bom_raw_materials(qty, scrap_qty)

		return item_dict

	def add_finished_goods_items_from_bom(self):
		if self.coating_order:
			fabric_details = frappe.db.get_value("Coating Order", self.coating_order, ["fabric_item", "fg_warehouse"], as_dict=1)
			item = frappe.get_cached_doc("Item", fabric_details.fabric_item)

			self.add_to_stock_entry_detail({
				item.name: {
					"to_warehouse": fabric_details.fg_warehouse,
					"qty": self.fg_completed_qty,
					"item_name": item.item_name,
					"description": item.description,
					"stock_uom": item.stock_uom,
				}
			})
		else:
			super().add_finished_goods_items_from_bom()


def update_stock_entry_from_work_order(stock_entry, work_order):
	stock_entry.pretreatment_order = work_order.pretreatment_order
	stock_entry.print_order = work_order.print_order
