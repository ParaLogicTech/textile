from frappe import _

def get_data():
	return {
		'fieldname': 'coating_order',
		'transactions': [
			{
				'label': _('Production'),
				'items': ['Stock Entry']
			},
		]
	}
