from . import __version__ as app_version

app_name = "digital_printing"
app_title = "Digital Printing"
app_publisher = "ParaLogic"
app_description = "Digital Printing ERP Application"
app_email = "info@paralogic.io"
app_license = "GNU General Public License (v3)"
required_apps = ["erpnext"]

app_include_js = "digital_printing.bundle.js"

after_install = "digital_printing.install.after_install"
notification_config = "digital_printing.notifications.get_notification_config"

doc_events = {
	"Customer": {
		"validate": "digital_printing.overrides.customer_hooks.customer_order_default_validate",
	},
	"Work Order": {
		"on_submit": "digital_printing.overrides.work_order_hooks.update_print_order_status",
		"on_cancel": "digital_printing.overrides.work_order_hooks.update_print_order_status",
		"update_work_order_qty": "digital_printing.overrides.work_order_hooks.update_print_order_status",
	},
	"UOM": {
		"before_rename": "digital_printing.overrides.uom_hooks.before_uom_rename",
	},
	"UOM Conversion Factor": {
		"on_update": "digital_printing.overrides.uom_hooks.on_uom_conversion_factor_update",
	}
}

override_doctype_class = {
	"Item": "digital_printing.overrides.item_hooks.ItemDP",
	"Sales Order": "digital_printing.overrides.sales_order_hooks.SalesOrderDP",
	"Delivery Note": "digital_printing.overrides.delivery_note_hooks.DeliveryNoteDP",
	"Sales Invoice": "digital_printing.overrides.sales_invoice_hooks.SalesInvoiceDP",
	"Stock Entry": "digital_printing.overrides.stock_entry_hooks.StockEntryDP",
	"Packing Slip": "digital_printing.overrides.packing_slip_hooks.PackingSlipDP",
}

override_doctype_dashboards = {
	"Item": "digital_printing.overrides.item_hooks.override_item_dashboard",
	"Customer": "digital_printing.overrides.customer_hooks.override_customer_dashboard",
	"Sales Order": "digital_printing.overrides.sales_order_hooks.override_sales_order_dashboard",
	"Delivery Note": "digital_printing.overrides.delivery_note_hooks.override_delivery_note_dashboard",
	"Sales Invoice": "digital_printing.overrides.sales_invoice_hooks.override_sales_invoice_dashboard",
	"Packing Slip": "digital_printing.overrides.packing_slip_hooks.override_packing_slip_dashboard",
}

doctype_js = {
	"Item": "overrides/item_hooks.js",
	"Customer": "overrides/customer_hooks.js",
	"Sales Order": "overrides/sales_order_hooks.js",
	"Stock Entry": "overrides/stock_entry_hooks.js",
}

update_item_override_fields = [
	"digital_printing.overrides.item_hooks.update_item_override_fields",
]

calculate_taxes_and_totals = [
    "digital_printing.overrides.taxes_and_totals_hooks.calculate_panel_qty"
]

update_work_order_from_sales_order = [
	"digital_printing.overrides.sales_order_hooks.set_print_order_reference_in_work_order",
	"digital_printing.overrides.sales_order_hooks.set_print_order_warehouses_in_work_order",
]

update_packing_slip_from_sales_order_mapper = [
	"digital_printing.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
]

update_delivery_note_from_sales_order_mapper = [
	"digital_printing.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
]

update_sales_invoice_from_sales_order_mapper = [
	"digital_printing.overrides.sales_order_hooks.map_print_order_reference_in_target_item",
]

update_sales_invoice_from_delivery_note_mapper = [
	"digital_printing.overrides.delivery_note_hooks.map_print_order_reference_in_sales_invoice_item",
]

update_delivery_note_from_packing_slip_mapper = [
	"digital_printing.overrides.packing_slip_hooks.map_print_order_reference_in_delivery_note_item",
]

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": {
			"name": ["in", [
				'Customer-printing_tab',
				'Customer-default_printing_uom',
				'Customer-default_printing_gap',
				'Customer-default_printing_qty_type',
				'Customer-default_printing_length_uom',
				'Item-print_item_type',
				'Item-sec_design_properties',
				'Item-design_name',
				'Item-design_width',
				'Item-design_height',
				'Item-column_break_9y2g0',
				'Item-design_gap',
				'Item-per_wastage',
				'Item-column_break_mjbrg',
				'Item-process_item',
				'Item-design_notes',
				'Item-sec_fabric_properties',
				'Item-fabric_material',
				'Item-fabric_type',
				'Item-column_break_fb7ki',
				'Item-fabric_width',
				'Item-fabric_gsm',
				'Item-column_break_vknw6',
				'Item-fabric_construction',
				'Item-fabric_item',
				'Item-fabric_item_name',
				'Item Group-print_item_type',
				'Item Source-print_item_type',
				'Brand-print_item_type',
				'Sales Order Item-print_order',
				'Sales Order Item-print_order_item',
				'Sales Order Item-panel_length_meter',
				'Sales Order Item-panel_qty',
				'Sales Order Item-show_panel_in_print',
				'Work Order-print_order',
				'Work Order-print_order_item',
				'Delivery Note Item-print_order',
				'Delivery Note Item-print_order_item',
				'Delivery Note Item-panel_length_meter',
				'Delivery Note Item-panel_qty',
				'Delivery Note Item-show_panel_in_print',
				'Sales Invoice Item-print_order',
				'Sales Invoice Item-print_order_item',
				'Sales Invoice Item-panel_length_meter',
				'Sales Invoice Item-panel_qty',
				'Sales Invoice Item-show_panel_in_print',
				'Packing Slip Item-print_order',
				'Packing Slip Item-print_order_item',
			]]
		}
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/digital_printing/css/digital_printing.css"
# app_include_js = "/assets/digital_printing/js/digital_printing.js"

# include js, css files in header of web template
# web_include_css = "/assets/digital_printing/css/digital_printing.css"
# web_include_js = "/assets/digital_printing/js/digital_printing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "digital_printing/public/scss/website"

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
#	"methods": "digital_printing.utils.jinja_methods",
#	"filters": "digital_printing.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "digital_printing.install.before_install"
# after_install = "digital_printing.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "digital_printing.uninstall.before_uninstall"
# after_uninstall = "digital_printing.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "digital_printing.notifications.get_notification_config"

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
#		"digital_printing.tasks.all"
#	],
#	"daily": [
#		"digital_printing.tasks.daily"
#	],
#	"hourly": [
#		"digital_printing.tasks.hourly"
#	],
#	"weekly": [
#		"digital_printing.tasks.weekly"
#	],
#	"monthly": [
#		"digital_printing.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "digital_printing.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "digital_printing.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "digital_printing.task.get_dashboard_data"
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
#	"digital_printing.auth.validate"
# ]
