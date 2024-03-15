import frappe
from frappe.utils import flt, cint
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


warehouse_fields = ['fabric_warehouse', 'source_warehouse', 'wip_warehouse', 'fg_warehouse']
print_process_fields = ["process_item", "process_item_name"]
fabric_fields = ["fabric_item", "fabric_item_name", "fabric_material", "fabric_width", "fabric_gsm"]
greige_fabric_fields = ["greige_" + f for f in fabric_fields]


class WorkOrderDP(WorkOrder):
	def on_submit(self):
		super().on_submit()
		self.update_pretreatment_order(validate_work_order_qty=True)
		self.update_print_order(validate_work_order_qty=True)

	def on_cancel(self):
		super().on_cancel()
		self.update_pretreatment_order()
		self.update_print_order()

	def update_status(self, status=False, from_doctype=None):
		super().update_status(status, from_doctype)
		self.update_pretreatment_order()
		self.update_print_order()

	def update_pretreatment_order(self, validate_work_order_qty=False):
		if self.get('pretreatment_order') and not frappe.flags.skip_pretreatment_order_status_update:
			doc = frappe.get_doc("Pretreatment Order", self.pretreatment_order)
			doc.set_production_packing_status(update=True)

			if validate_work_order_qty:
				doc.validate_work_order_qty(from_doctype=self.doctype)

			doc.set_status(update=True)
			doc.notify_update()

	def update_print_order(self, validate_work_order_qty=False):
		if self.get('print_order') and self.get('print_order_item') and not frappe.flags.skip_print_order_status_update:
			doc = frappe.get_doc("Print Order", self.print_order)
			doc.set_production_packing_status(update=True)

			if validate_work_order_qty:
				doc.validate_work_order_qty(from_doctype=self.doctype,
					row_names=[self.print_order_item])

			doc.set_status(update=True)
			doc.notify_update()

	def set_required_items(self, reset_only_qty=False):
		super().set_required_items(reset_only_qty)

		if not reset_only_qty and self.get("print_order"):
			order = get_print_order_details(self.print_order)
			for d in self.get("required_items"):
				if d.item_code == order.fabric_item:
					d.source_warehouse = order.fabric_warehouse if order.skip_transfer else order.wip_warehouse

		if not reset_only_qty and self.get("pretreatment_order"):
			order = frappe.db.get_value("Pretreatment Order", self.pretreatment_order,
				["greige_fabric_item", "fabric_warehouse"], as_dict=1)

			for d in self.get("required_items"):
				if d.item_code == order.greige_fabric_item:
					d.source_warehouse = order.fabric_warehouse


def update_work_order_on_create(work_order, args=None):
	if args and args.get("pretreatment_order"):
		work_order.pretreatment_order = args.get("pretreatment_order")
	if args and args.get("print_order"):
		work_order.print_order = args.get("print_order")
	if args and args.get("print_order_item"):
		work_order.print_order_item = args.get("print_order_item")

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
		pretreatment_order_details = get_pretreatment_order_details(work_order.pretreatment_order)

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
		print_order_details = get_print_order_details(work_order.print_order)

		work_order.skip_transfer = 1
		work_order.from_wip_warehouse = 0
		work_order.packing_slip_required = cint(
			not print_order_details.is_internal_customer and print_order_details.packing_slip_required
		)

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


def get_pretreatment_order_details(pretreatment_order):
	fields = ["packing_slip_required", "delivery_required"] + greige_fabric_fields + warehouse_fields
	return frappe.db.get_value("Pretreatment Order", pretreatment_order, fields, as_dict=1)


def get_print_order_details(print_order):
	def generator():
		fields = ["packing_slip_required", "is_internal_customer", "skip_transfer"] + fabric_fields + print_process_fields + warehouse_fields
		return frappe.db.get_value("Print Order", print_order, fields, as_dict=1)

	return frappe.local_cache("print_order_details_wo_from_so", print_order, generator)


def update_job_card_on_create(job_card):
	pretreatment_order = frappe.db.get_value("Work Order", job_card.work_order, "pretreatment_order", cache=1)
	job_card.pretreatment_order = pretreatment_order


def work_order_list_query(user):
	if not user:
		user = frappe.session.user

	# show only work orders to user those linked with only pretreatment orders/print orders based on the user roles
	user_has_roles = frappe.get_roles(user)
	conditions = []
	if "Pretreatment Production User" not in user_has_roles:
		conditions.append("(NOT(`tabWork Order`.pretreatment_order IS NOT NULL AND `tabWork Order`.pretreatment_order != ''))")
	if "Print Production User" not in user_has_roles:
		conditions.append("(NOT(`tabWork Order`.print_order IS NOT NULL AND `tabWork Order`.print_order != ''))")

	conditions = f"({' AND '.join(conditions)})" if conditions else ""
	return conditions
