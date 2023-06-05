import frappe
from frappe import _


def get_data():

	return {
		'fieldname': 'print_order',
		'internal_links': {
			'Item': ['items', 'item_code'],
			'BOM': ['items', 'design_bom'],
		},
		'transactions': [
			{
				'label': _("Design Item"),
				'items': ['Item', 'BOM']
			},
			{
				'label': _("Order & Billing"),
				'items': ['Sales Order', 'Sales Invoice']
			},
			{
				'label': _("Production"),
				'items': ['Work Order', 'Stock Entry']
			},
			{
				'label': _("Delivery"),
				'items': ['Packing Slip', 'Delivery Note']
			}
		]
	}
