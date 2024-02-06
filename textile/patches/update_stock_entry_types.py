import frappe
from textile.install import populate_stock_entry_types


def execute():
	populate_stock_entry_types()
