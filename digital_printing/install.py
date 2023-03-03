import frappe


fabric_types = [
	'Brocade', 'Heavy', 'Egyptian', 'Golden Organza', 'Cambric', 'Crinkle Chiffon', 'Upholstery',
	'Interlock', 'Parachute', 'Velour', 'Raw', 'Slub', 'Latha', 'SwissFoil', 'Flat Back Mesh', 'Lawn', 'Chiffon',
	'Twill', 'Jacquard', 'Spunbond', 'Heavy Twill', 'Charmeuse', 'Suede', 'Karandi', 'Organza', 'Bemberg', 'Satin',
	'Fleece', 'Bemberg Chiffon', 'Medium Twill', 'Georgette', 'RTW Poly Satin', 'Coarse Weave', 'Medium Weave',
	'Tissue', 'Heavy Felt', 'Katan', 'Herringbone', 'Raw Silk', 'Thai Silk', 'Dobby Net', 'Linen', 'Crepe', 'Valvet',
	'Plain', 'Canvas', 'Moss Crepe', 'Jamawar', 'Net', 'Khaddar', 'Medium', 'Poplin', 'Monar'
]


fabric_materials = ['Viscose', 'Silk', 'Polyester', 'Cotton']


def after_install():
	populate_fabric_type()
	populate_fabric_material()
	create_printing_uom()


def populate_fabric_type():
	for name in fabric_types:
		if not frappe.db.exists("Fabric Type", name):
			frappe.get_doc({
				"doctype": "Fabric Type",
				"fabric_type": name
			}).save()


def populate_fabric_material():
	for name in fabric_materials:
		if not frappe.db.exists("Fabric Material", name):
			frappe.get_doc({
				"doctype": "Fabric Material",
				"fabric_material": name
			}).save()


def create_printing_uom():
	if not frappe.db.exists("UOM", "Panel"):
		frappe.get_doc({
			"doctype": "UOM",
			"uom_name": "Panel"
		}).save(ignore_permissions=True)
