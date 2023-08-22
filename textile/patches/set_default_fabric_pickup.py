import frappe
from frappe.utils.fixtures import sync_fixtures


def execute():
	sync_fixtures(app="textile")
	frappe.db.sql("update `tabItem` set fabric_per_pickup = 100")
	frappe.db.sql("update `tabPrint Order` set fabric_per_pickup = 100")
