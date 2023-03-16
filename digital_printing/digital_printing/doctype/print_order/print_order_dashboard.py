import frappe
from frappe import _

def get_data():

	return {
		'fieldname': 'print_order',
		'transactions': [
			{
				'label': _("Reference"),
				'items': ['Sales Order']
			},
		]
	}
