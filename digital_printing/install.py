import frappe


fabric_materials = [
	('Cotton', 'Co'),
	('Polyester', 'Po'),
	('Silk', 'Se'),
	('Viscose', 'Vi'),
	('Cotton/Polyester', 'Cp'),
	('Cotton/Silk', 'Cs'),
	('Cotton/Viscose', 'Cv'),
]


fabric_types = [
	('Bemberg', 'Be'),
	('Brocade', 'Br'),
	('Cambric', 'Ca'),
	('Canvas', 'Cv'),
	('Charmeuse', 'Cm'),
	('Chiffon', 'Cf'),
	('Crepe', 'Ce'),
	('Crinkle', 'Cr'),
	('Denim', 'De'),
	('Dobby', 'Do'),
	('Felt', 'Fe'),
	('Fleece', 'Dl'),
	('Gauze', 'Ga'),
	('Georgette', 'Ge'),
	('Jacquard', 'Ja'),
	('Jamawar', 'Jw'),
	('Karandi', 'Kr'),
	('Khaddar', 'Kh'),
	('Knit', 'Kn'),
	('Lace', 'Lc'),
	('Latha', 'Lt'),
	('Lawn', 'La'),
	('Linen', 'Li'),
	('Muslin', 'Mu'),
	('Net', 'Ne'),
	('Nonwoven', 'Nw'),
	('Organza', 'Or'),
	('Parachute', 'Pa'),
	('Percale', 'Pe'),
	('Plain', 'Pl'),
	('Poplin', 'Po'),
	('Satin', 'Sa'),
	('Silk', 'Si'),
	('Slub', 'Sl'),
	('Suede', 'Su'),
	('Terry', 'Te'),
	('Tissue', 'Ti'),
	('Twill', 'Tw'),
	('Upholstery', 'Up'),
	('Velvet', 'Vv'),
	('Voile', 'Vo'),
]


def after_install():
	from digital_printing.digital_printing.doctype.print_order.print_order import update_conversion_factor_global_defaults

	populate_fabric_material()
	populate_fabric_type()
	create_printing_uom()
	update_conversion_factor_global_defaults()


def populate_fabric_material():
	for name, abbr in fabric_materials:
		if not frappe.db.exists("Fabric Material", name):
			frappe.get_doc({
				"doctype": "Fabric Material",
				"fabric_material": name,
				"abbreviation": abbr,
			}).save()


def populate_fabric_type():
	for name, abbr in fabric_types:
		if not frappe.db.exists("Fabric Type", name):
			frappe.get_doc({
				"doctype": "Fabric Type",
				"fabric_type": name,
				"abbreviation": abbr,
			}).save()


def create_printing_uom():
	if not frappe.db.exists("UOM", "Panel"):
		frappe.get_doc({
			"doctype": "UOM",
			"uom_name": "Panel"
		}).save(ignore_permissions=True)
