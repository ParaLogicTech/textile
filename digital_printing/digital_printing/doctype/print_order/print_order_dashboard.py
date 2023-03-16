import frappe
from frappe import _

def get_data():

	return {
		'fieldname': 'print_order',
		'internal_links': {
			'Item': ['items', 'item_code'],
			'BOM': ['items', 'design_bom']
		},
		'transactions': [
			{
				'label': _("Reference"),
				'items': ['Item', 'BOM', 'Sales Order']
			},
		]
	}
