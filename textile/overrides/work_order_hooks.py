import frappe
from frappe.utils import flt, cint
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


warehouse_fields = ['fabric_warehouse', 'source_warehouse', 'wip_warehouse', 'fg_warehouse']
print_process_fields = ["process_item", "process_item_name"]
fabric_fields = ["fabric_item", "fabric_item_name", "fabric_material", "fabric_width", "fabric_gsm"]
greige_fabric_fields = ["greige_" + f for f in fabric_fields]


class WorkOrderDP(WorkOrder):
	def set_required_items(self, reset_only_qty=False):
		super().set_required_items(reset_only_qty)

		if not reset_only_qty and self.get("print_order"):
			fabric_item = frappe.db.get_value("Print Order", self.print_order, "fabric_item", cache=1)
			for d in self.get("required_items"):
				if d.item_code == fabric_item:
					d.source_warehouse = self.wip_warehouse

		if not reset_only_qty and self.get("pretreatment_order"):
			order = frappe.db.get_value("Pretreatment Order", self.pretreatment_order,
				["greige_fabric_item", "fabric_warehouse"], as_dict=1)

			for d in self.get("required_items"):
				if d.item_code == order.greige_fabric_item:
					d.source_warehouse = order.fabric_warehouse


def update_work_order_on_create(work_order, args=None):
	def get_pretreatment_order_details():
		fields = ["packing_slip_required", "delivery_required"] + greige_fabric_fields + warehouse_fields
		return frappe.db.get_value("Pretreatment Order", work_order.pretreatment_order, fields, as_dict=1)

	def get_print_order_details():
		fields = ["packing_slip_required"] + fabric_fields + print_process_fields + warehouse_fields
		return frappe.db.get_value("Print Order", work_order.print_order, fields, as_dict=1)

	if args and args.get("pretreatment_order"):
		work_order.pretreatment_order = args.get("pretreatment_order")

	# Set Order Reference
	if work_order.get('sales_order_item'):
		so_item = frappe.db.get_value("Sales Order Item", work_order.sales_order_item,
			["pretreatment_order", "print_order", "print_order_item"], as_dict=1)
		if so_item:
			work_order.pretreatment_order = so_item.pretreatment_order
			work_order.print_order = so_item.print_order
			work_order.print_order_item = so_item.print_order_item

	# Set Preatreatment Order related values
	if work_order.get('pretreatment_order'):
		pretreatment_order_details = get_pretreatment_order_details()

		work_order.skip_transfer = 0
		work_order.from_wip_warehouse = 0
		work_order.packing_slip_required = cint(
			pretreatment_order_details.delivery_required and pretreatment_order_details.packing_slip_required
		)

		for warehouse_field in warehouse_fields:
			warehouse = pretreatment_order_details.get(warehouse_field)
			if warehouse:
				work_order.set(warehouse_field, warehouse)

		for field in fabric_fields:
			work_order.set(field, pretreatment_order_details.get("greige_" + field))

	# Set Print Order related values
	if work_order.get('print_order'):
		print_order_details = frappe.local_cache("print_order_details_wo_from_so", work_order.print_order,
			get_print_order_details)

		work_order.skip_transfer = 1
		work_order.from_wip_warehouse = 0
		work_order.packing_slip_required = print_order_details.packing_slip_required

		for warehouse_field in warehouse_fields:
			warehouse = print_order_details.get(warehouse_field)
			if warehouse:
				work_order.set(warehouse_field, warehouse)

		for field in fabric_fields + print_process_fields:
			work_order.set(field, print_order_details.get(field))

	# Set max qty
	if work_order.get('print_order_item'):
		work_order.max_qty = flt(frappe.db.get_value("Print Order Item", work_order.print_order_item,
			"stock_fabric_length", cache=1))


def on_work_order_update_status(work_order, hook, status=None):
	if work_order.get('pretreatment_order') and not frappe.flags.skip_pretreatment_order_status_update:
		doc = frappe.get_doc("Pretreatment Order", work_order.pretreatment_order)
		doc.set_production_packing_status(update=True)

		if hook != 'update_status':
			doc.validate_work_order_qty(from_doctype=work_order.doctype)

		doc.set_status(update=True)
		doc.notify_update()

	if work_order.get('print_order') and work_order.get('print_order_item') and not frappe.flags.skip_print_order_status_update:
		doc = frappe.get_doc("Print Order", work_order.print_order)
		doc.set_production_packing_status(update=True)

		if hook != 'update_status':
			doc.validate_work_order_qty(from_doctype=work_order.doctype, row_names=[work_order.print_order_item])

		doc.set_status(update=True)
		doc.notify_update()
