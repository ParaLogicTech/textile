import frappe


def execute():
	frappe.rename_doc("Module Def", "Digital Printing", "Fabric Printing", force=1)
	frappe.rename_doc("Workspace", "Digital Printing", "Fabric Printing", force=1)
	frappe.rename_doc("DocType", "Digital Printing Settings", "Fabric Printing Settings", force=1)