import frappe
import io
from frappe.utils import cint
from frappe.core.doctype.file.utils import get_local_image


@frappe.whitelist()
def get_rotated_image(file, angle=90, height=143):
	file_name = frappe.db.get_value("File", filters={"file_url": file})
	if not file_name:
		raise frappe.DoesNotExistError

	angle = cint(angle)
	height = cint(height)

	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")

	original_image, original_filename, ext = get_local_image(file)
	image_format = original_image.format

	scaling_factor = height / original_image.width
	width = original_image.height * scaling_factor

	height = cint(height * 2)
	width = cint(width * 2)

	original_image.thumbnail((height, width))

	modified_image = original_image.rotate(angle, expand=True)

	rotated_filename = original_filename.split("/")[-1]
	rotated_filename = f"{rotated_filename}_rotated.{ext}"

	output = io.BytesIO()
	modified_image.save(
		output,
		format=image_format or "jpeg",
		quality=70,
	)

	frappe.response.filename = rotated_filename
	frappe.response.filecontent = output.getvalue()
	frappe.response.type = "download"
	frappe.response.display_content_as = "inline"
