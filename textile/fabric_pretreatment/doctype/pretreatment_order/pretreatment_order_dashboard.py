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
				'items': ['Work Order', 'Job Card', 'Stock Entry']
			},
			{
				'label': _("Delivery"),
				'items': ['Packing Slip', 'Delivery Note']
			},
			{
				'label': _("Subcontracting"),
				'items': ['Purchase Order', 'Purchase Receipt']
			},
			{
				'label': _("Printing"),
				'items': ['Print Order']
			}
		]
	}
