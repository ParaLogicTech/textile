import frappe
from frappe import _
from frappe.utils import cint
from frappe.core.doctype.file.utils import get_local_image
from frappe.utils.user import is_website_user
from frappe.core.doctype.file.utils import delete_file
from werkzeug.utils import send_file
import io
import os
import mimetypes


@frappe.whitelist()
def get_rotated_image(file):
	if not file:
		frappe.throw(_("File URL not provided"))

	file_id = get_file_id(file)
	if not file_id:
		raise frappe.DoesNotExistError

	file_doc = frappe.get_doc("File", file_id)
	if file_doc.is_private and is_website_user():
		file_doc.raise_no_permission_to("read")

	rotated_image_url = get_rotated_image_url(file)

	if rotated_image_url and os.path.isfile(get_file_path(rotated_image_url)):
		rotated_file_path = get_file_path(rotated_image_url)
		rotated_filename = os.path.basename(rotated_file_path)
		output = open(rotated_file_path, "rb")
	else:
		rotated_filename, output = save_rotated_image_file(file, file_doc)

	return send_file(
		output,
		environ=frappe.local.request.environ,
		mimetype=mimetypes.guess_type(rotated_filename)[0] or "image/jpeg",
		download_name=rotated_filename,
	)


def get_file_id(file_url):
	files = frappe.db.sql("""
		select name, file_url
		from `tabFile`
		where file_url = %s
		order by if(attached_to_doctype = 'Print Order', 0, 1), creation
	""", file_url, as_dict=1)

	file_id = None
	for d in files:
		if d.file_url == file_url:
			file_id = d.name
			break

	return file_id


def get_rotated_image_url(file_url):
	files = frappe.get_all("File", filters={
		"file_url": file_url, "rotated_image": ["is", "set"]
	}, fields=["file_url", "rotated_image"])

	rotated_image_url = None
	for d in files:
		if d.file_url == file_url:
			rotated_image_url = d.rotated_image
			break

	return rotated_image_url


def save_rotated_image_file(file, file_doc):
	rotated_filename, output = make_rotated_image(file)

	path = os.path.abspath(frappe.get_site_path(
		"private" if file_doc.is_private else "public",
		"files",
		rotated_filename.lstrip("/"))
	)

	with open(path, "wb") as f:
		f.write(output.getbuffer())
		output.seek(0)

	if file_doc.is_private:
		rotated_image_url = "/private/files/" + rotated_filename
	else:
		rotated_image_url = "/files/" + rotated_filename

	file_doc.db_set("rotated_image", rotated_image_url)
	frappe.db.commit()

	return rotated_filename, output


def make_rotated_image(file):
	angle = 90
	view_height = 150

	original_image, original_filename, ext = get_local_image(file)
	image_format = original_image.format

	scaling_factor = view_height / original_image.width
	width = original_image.height * scaling_factor

	height = cint(view_height * 2)
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
	output.seek(0)

	return rotated_filename, output


def get_file_path(file_url):
	if file_url.startswith("/private"):
		file_url_path = (file_url.lstrip("/"),)
	else:
		file_url_path = ("public", file_url.lstrip("/"))

	file_path = frappe.get_site_path(*file_url_path)
	return file_path


def delete_file_data_content(doc, only_thumbnail=False):
	doc.delete_file_from_filesystem(only_thumbnail=only_thumbnail)
	if doc.rotated_image:
		delete_file(doc.rotated_image)
