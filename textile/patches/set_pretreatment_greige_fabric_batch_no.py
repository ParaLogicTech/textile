import frappe


def execute():
	frappe.db.sql("""
		update `tabWork Order`
		set auto_select_batches_in_stock_entry = 1
		where print_order is not null and print_order != ''
	""")

	frappe.db.sql("""
		update `tabPretreatment Order` o
		inner join `tabItem` i on i.name = o.greige_fabric_item
		set o.greige_fabric_has_batch_no = i.has_batch_no
	""")

	batch_orders = frappe.get_all("Pretreatment Order", filters={
		"greige_fabric_has_batch_no": 1, "docstatus": 1, "production_status": "Produced"
	}, pluck="name")

	for pto_name in batch_orders:
		work_orders = frappe.get_all("Work Order", filters={"pretreatment_order": pto_name}, pluck="name")
		if not work_orders:
			continue

		pretreatment_order = frappe.get_doc("Pretreatment Order", pto_name)

		batch_nos = frappe.db.sql_list("""
			select distinct i.batch_no
			from `tabStock Entry Detail` i
			inner join `tabStock Entry` ste on ste.name = i.parent
			where ste.docstatus = 1
				and ste.purpose = 'Manufacture'
				and ste.work_order in %s
				and i.item_code = %s
				and ifnull(i.s_warehouse, '') != ''
				and ifnull(i.t_warehouse, '') = ''
		""", [work_orders, pretreatment_order.greige_fabric_item])

		if len(batch_nos) == 1:
			pretreatment_order.db_set("greige_fabric_batch_no", batch_nos[0], update_modified=False)
			pretreatment_order.update_work_order_greige_fabric_batch_no()
