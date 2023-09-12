import frappe


def execute():
	duplicates = frappe.db.sql("""
		select file_url, attached_to_doctype, attached_to_name
		from `tabFile`
		where is_folder = 0
			and ifnull(attached_to_doctype) != ''
			and ifnull(attached_to_name) != ''
		group by file_url, attached_to_doctype, attached_to_name
		having count(*) > 1
	""", as_dict=1)

	if not duplicates:
		print("No Duplicate Attachments")
		return

	print("{0} distinct duplicate file attachments found".format(len(duplicates)))

	for dup in duplicates:
		files = frappe.get_all("File", filters=dup, fields="*")
		if len(files) <= 1:
			frappe.throw("Something wrong with the patch")

		to_keep = files[0].name
		for file in files:
			if file.get("rotated_image"):
				to_keep = file.name

		delete_filters = dup.copy()
		delete_filters["name"] = ["!=", to_keep]
		frappe.db.delete("File", filters=delete_filters)
