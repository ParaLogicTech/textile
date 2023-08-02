import frappe


def execute():
	for doctype in ("Packing Slip", "Delivery Note", "Sales Invoice"):
		frappe.db.sql("""
			UPDATE `tab{doctype} Item` i
			INNER JOIN `tabPrint Order` pro ON pro.name = i.print_order
			SET
				i.is_return_fabric = IF(i.item_code = pro.fabric_item, 1, 0)
		""".format(doctype=doctype))

	frappe.db.commit()
