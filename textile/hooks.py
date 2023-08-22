from . import __version__ as app_version

app_name = "textile"
app_title = "Textile"
app_publisher = "ParaLogic"
app_description = "Textile ERP Application"
app_email = "info@paralogic.io"
app_license = "GNU General Public License (v3)"
required_apps = ["erpnext"]

app_include_js = "textile.bundle.js"
app_include_css = "textile.bundle.css"

after_install = "textile.install.after_install"
notification_config = "textile.notifications.get_notification_config"

doc_events = {
	"Customer": {
		"validate": "textile.overrides.customer_hooks.customer_order_default_validate",
	},
	"Work Order": {
		"on_submit": "textile.overrides.work_order_hooks.update_print_order_status",
		"on_cancel": "textile.overrides.work_order_hooks.update_print_order_status",
		"update_status": "textile.overrides.work_order_hooks.update_print_order_status",
	},
	"UOM": {
		"before_rename": "textile.overrides.uom_hooks.before_uom_rename",
	},
	"UOM Conversion Factor": {
		"on_update": "textile.overrides.uom_hooks.on_uom_conversion_factor_update",
	},
	"BOM": {
		"on_cancel": "textile.overrides.bom_hooks.on_bom_cancel",
	}
}

override_doctype_class = {
	"Item": "textile.overrides.item_hooks.ItemDP",
	"Sales Order": "textile.overrides.sales_order_hooks.SalesOrderDP",
	"Delivery Note": "textile.overrides.delivery_note_hooks.DeliveryNoteDP",
	"Sales Invoice": "textile.overrides.sales_invoice_hooks.SalesInvoiceDP",
	"Packing Slip": "textile.overrides.packing_slip_hooks.PackingSlipDP",
	"Work Order": "textile.overrides.work_order_hooks.WorkOrderDP",
	"Stock Entry": "textile.overrides.stock_entry_hooks.StockEntryDP",
}

override_doctype_dashboards = {
	"Item": "textile.overrides.item_hooks.override_item_dashboard",
	"Customer": "textile.overrides.customer_hooks.override_customer_dashboard",
	"Sales Order": "textile.overrides.sales_order_hooks.override_sales_order_dashboard",
	"Delivery Note": "textile.overrides.delivery_note_hooks.override_delivery_note_dashboard",
	"Sales Invoice": "textile.overrides.sales_invoice_hooks.override_sales_invoice_dashboard",
	"Packing Slip": "textile.overrides.packing_slip_hooks.override_packing_slip_dashboard",
}

doctype_js = {
	"Item": "overrides/item_hooks.js",
	"Customer": "overrides/customer_hooks.js",
	"Sales Order": "overrides/sales_order_hooks.js",
	"Stock Entry": "overrides/stock_entry_hooks.js",
	"Packing Slip": "overrides/packing_slip_hooks.js",
	"Delivery Note": "overrides/delivery_note_hooks.js",
	"Sales Invoice": "overrides/sales_invoice_hooks.js",
}

doctype_list_js = {
	"Work Order": "overrides/work_order_list_hooks.js"
}

update_item_override_fields = [
	"textile.overrides.item_hooks.update_item_override_fields",
]

calculate_taxes_and_totals = [
	"textile.overrides.taxes_and_totals_hooks.calculate_panel_qty_for_taxes_and_totals"
]

update_work_order_from_sales_order = [
	"textile.overrides.work_order_hooks.update_work_order_from_sales_order",
]

update_stock_entry_from_work_order = [
	"textile.overrides.stock_entry_hooks.update_stock_entry_from_work_order"
]

update_packing_slip_from_sales_order_mapper = [
	"textile.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
	"textile.overrides.packing_slip_hooks.update_packing_slip_from_sales_order_mapper",
]

update_delivery_note_from_sales_order_mapper = [
	"textile.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
]

update_sales_invoice_from_sales_order_mapper = [
	"textile.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
]

update_sales_invoice_from_delivery_note_mapper = [
	"textile.overrides.delivery_note_hooks.map_print_order_reference_in_sales_invoice_item",
]

update_delivery_note_from_packing_slip_mapper = [
	"textile.overrides.packing_slip_hooks.map_print_order_reference_in_delivery_note_item",
]

delete_file_data_content = "textile.rotated_image.delete_file_data_content"


scheduler_events = {
	"hourly_long": [
		"textile.textile.doctype.textile_email_digest.textile_email_digest.send_textile_email_digest",
	],
}

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": {
			"name": ["in", [
				'File-rotated_image',

				'Customer-printing_tab',
				'Customer-default_printing_uom',
				'Customer-default_printing_gap',
				'Customer-default_printing_qty_type',
				'Customer-default_printing_length_uom',

				'Item-textile_item_type',
				'Item-process_component',
				'Item-consumption_by_fabric_weight',

				'Item-print_process_properties',
				'Item-softener_item_required',
				'Item-column_break_wdop0',
				'Item-coating_item_required',
				'Item-column_break_ceseq',
				'Item-sublimation_paper_item_required',
				'Item-column_break_0brhk',
				'Item-protection_paper_item_required',

				'Item-sec_design_properties',
				'Item-design_width',
				'Item-design_height',
				'Item-column_break_9y2g0',
				'Item-design_gap',
				'Item-per_wastage',
				'Item-column_break_mjbrg',
				'Item-design_notes',

				'Item-sec_fabric_properties',
				'Item-fabric_material',
				'Item-fabric_type',
				'Item-column_break_fb7ki',
				'Item-fabric_width',
				'Item-fabric_gsm',
				'Item-column_break_vknw6',
				'Item-fabric_construction',
				'Item-fabric_per_pickup',
				'Item-column_break_zr6ct',
				'Item-fabric_item',
				'Item-fabric_item_name',

				'Item-paper_properties',
				'Item-paper_width',
				'Item-column_break_ysj7q',
				'Item-paper_gsm',

				'Item Group-textile_item_type',
				'Item Source-textile_item_type',
				'Brand-textile_item_type',

				'Sales Order Item-print_order',
				'Sales Order Item-print_order_item',
				'Sales Order Item-panel_length_meter',
				'Sales Order Item-panel_qty',
				'Sales Order Item-panel_based_qty',

				'Delivery Note Item-print_order',
				'Delivery Note Item-print_order_item',
				'Delivery Note Item-panel_length_meter',
				'Delivery Note Item-panel_qty',
				'Delivery Note Item-panel_based_qty',
				'Delivery Note Item-is_return_fabric',

				'Sales Invoice Item-print_order',
				'Sales Invoice Item-print_order_item',
				'Sales Invoice Item-panel_length_meter',
				'Sales Invoice Item-panel_qty',
				'Sales Invoice Item-panel_based_qty',
				'Sales Invoice Item-is_return_fabric',

				'Packing Slip Item-print_order',
				'Packing Slip Item-print_order_item',
				'Packing Slip Item-column_break_zytx5',
				'Packing Slip Item-panel_length_meter',
				'Packing Slip Item-panel_qty',
				'Packing Slip Item-panel_based_qty',
				'Packing Slip Item-is_return_fabric',

				'Work Order-print_order',
				'Work Order-print_order_item',

				'Work Order-fabric_details',
				'Work Order-fabric_item',
				'Work Order-fabric_item_name',
				'Work Order-column_break_tdpdc',
				'Work Order-fabric_material',
				'Work Order-fabric_width',
				'Work Order-column_break_xvc9e',
				'Work Order-fabric_gsm',

				'Work Order-process_details',
				'Work Order-process_item',
				'Work Order-column_break_4pknu',
				'Work Order-process_item_name',

				'Stock Entry-print_order',
				'Stock Entry-fabric_printer',
			]]
		}
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/textile/css/textile.css"
# app_include_js = "/assets/textile/js/textile.js"

# include js, css files in header of web template
# web_include_css = "/assets/textile/css/textile.css"
# web_include_js = "/assets/textile/js/textile.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "textile/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "textile.utils.jinja_methods",
#	"filters": "textile.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "textile.install.before_install"
# after_install = "textile.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "textile.uninstall.before_uninstall"
# after_uninstall = "textile.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "textile.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"textile.tasks.all"
#	],
#	"daily": [
#		"textile.tasks.daily"
#	],
#	"hourly": [
#		"textile.tasks.hourly"
#	],
#	"weekly": [
#		"textile.tasks.weekly"
#	],
#	"monthly": [
#		"textile.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "textile.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "textile.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "textile.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]


# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"textile.auth.validate"
# ]
