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
				'label': _("Sales"),
				'items': ['Sales Order','Delivery Note', 'Sales Invoice']
			},
			{
				'label': _("Production"),
				'items': [ 'Work Order', 'Packing Slip']
			}
		]
	}
