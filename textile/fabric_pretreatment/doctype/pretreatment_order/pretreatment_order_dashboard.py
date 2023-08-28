import frappe
from frappe import _


def get_data():
	return {
		'fieldname': 'pretreatment_order',
		'transactions': [
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
