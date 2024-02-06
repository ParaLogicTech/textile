import frappe

stock_entry_types = [
	("Fabric Transfer for Printing", "Material Transfer for Manufacture"),
	("Fabric Transfer for Pretreatment", "Material Transfer for Manufacture"),
	("Fabric Coating", "Manufacture"),
	("Fabric Printing", "Manufacture"),
	("Fabric Pretreatment", "Manufacture"),
	("Pretreatment Operation", "Material Consumption for Manufacture"),
]

customs_tariff_numbers = [
	{
		"tariff_number": "5208.1100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Unbleached, Plain Weave, Weighing Not Over 100 G/M2",
	},
	{
		"tariff_number": "5208.1200",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Unbleached, Plain Weave, Weighing Over 100 G/M2 But Not Over 200 G/M2",
	},
	{
		"tariff_number": "5209.1100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Unbleached, Plain Weave, Weighing Over 200 G/M2",
	},
	{
		"tariff_number": "5208.2100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Bleached, Plain Weave, Weighing Not Over 100 G/M2",
	},
	{
		"tariff_number": "5208.2200",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Bleached, Plain Weave, Weighing Over 100 G/M2 But Not Over 200 G/M2",
	},
	{
		"tariff_number": "5209.2100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Bleached, Plain Weave, Weighing Over 200 G/M2",
	},
	{
		"tariff_number": "5208.5100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Printed, Plain Weave, Weighing Not Over 100 G/M2",
	},
	{
		"tariff_number": "5208.5200",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Printed, Plain Weave, Weighing Over 100 G/M2 But Not Over 200 G/M2",
	},
	{
		"tariff_number": "5209.5100",
		"description": "Woven Fabrics Of Cotton, 85% Or More Cotton By Weight, Printed, Plain Weave, Weighing Over 200 G/M2",
	},
	{
		"tariff_number": "5407.5100",
		"description": "Woven Fabrics Of Synthetic Filaments , 85% Or More By Weight Of Textured Polyester Filaments, Unbleached Or Bleached",
	},
	{
		"tariff_number": "5407.5400",
		"description": "Woven Fabrics Of Synthetic Filaments , 85% Or More By Weight Of Textured Polyester Filaments, Printed",
	},
	{
		"tariff_number": "5007.9000",
		"description": "Woven Fabrics Of Silk Or Silk Waste",
	},
	{
		"tariff_number": "5408.2100",
		"description": "Woven Fabrics Of Artificial Filaments (Not Of Viscose Rayon From High Tenacity Yarn), 85% Or More (Wt) Artificial Filament, Unbleached Or Bleached",
	},
	{
		"tariff_number": "5408.2400",
		"description": "Woven Fabrics Of Artificial Filaments (Not Of Viscose Rayon From High Tenacity Yarn), 85% Or More (Wt) Artificial Filament, Printed",
	},
]

cotton_greige_tariff = [
	{'customs_tariff_number': '5208.1100', 'gsm_low': 0, 'gsm_high': 100},
	{'customs_tariff_number': '5208.1200', 'gsm_low': 100, 'gsm_high': 200},
	{'customs_tariff_number': '5209.1100', 'gsm_low': 200},
]

cotton_ready_tariff = [
	{'customs_tariff_number': '5208.2100', 'gsm_low': 0, 'gsm_high': 100},
	{'customs_tariff_number': '5208.2200', 'gsm_low': 100, 'gsm_high': 200},
	{'customs_tariff_number': '5209.2100', 'gsm_low': 200},
]

cotton_printed_tariff = [
	{'customs_tariff_number': '5208.5100', 'gsm_low': 0, 'gsm_high': 100},
	{'customs_tariff_number': '5208.5200', 'gsm_low': 100, 'gsm_high': 200},
	{'customs_tariff_number': '5209.5100', 'gsm_low': 200},
]

polyester_greige_ready_tariff = [
	{'customs_tariff_number': '5407.5100'},
]

polyester_printed_tariff = [
	{'customs_tariff_number': '5407.5400'},
]

silk_tariff = [
	{'customs_tariff_number': '5007.9000'},
]

viscose_greige_ready_tariff = [
	{'customs_tariff_number': '5408.2100'},
]

viscose_printed_tariff = [
	{'customs_tariff_number': '5408.2400'},
]

fabric_materials = [
	{
		'fabric_material': 'Cotton',
		'abbreviation': 'Co',
		'greige_fabric_tariff': cotton_greige_tariff,
		'ready_fabric_tariff': cotton_ready_tariff,
		'printed_fabric_tariff': cotton_printed_tariff,
	},
	{
		'fabric_material': 'Polyester',
		'abbreviation': 'Po',
		'greige_fabric_tariff': polyester_greige_ready_tariff,
		'ready_fabric_tariff': polyester_greige_ready_tariff,
		'printed_fabric_tariff': polyester_printed_tariff,
	},
	{
		'fabric_material': 'Silk',
		'abbreviation': 'Se',
		'greige_fabric_tariff': silk_tariff,
		'ready_fabric_tariff': silk_tariff,
		'printed_fabric_tariff': silk_tariff,
	},
	{
		'fabric_material': 'Viscose',
		'abbreviation': 'Vi',
		'greige_fabric_tariff': viscose_greige_ready_tariff,
		'ready_fabric_tariff': viscose_greige_ready_tariff,
		'printed_fabric_tariff': viscose_printed_tariff,
	},
	{
		'fabric_material': 'Cotton/Polyester',
		'abbreviation': 'Cp',
		'greige_fabric_tariff': cotton_greige_tariff,
		'ready_fabric_tariff': cotton_ready_tariff,
		'printed_fabric_tariff': cotton_printed_tariff,
	},
	{
		'fabric_material': 'Cotton/Silk',
		'abbreviation': 'Cs',
		'greige_fabric_tariff': cotton_greige_tariff,
		'ready_fabric_tariff': cotton_ready_tariff,
		'printed_fabric_tariff': cotton_printed_tariff,
	},
	{
		'fabric_material': 'Cotton/Viscose',
		'abbreviation': 'Cv',
		'greige_fabric_tariff': cotton_greige_tariff,
		'ready_fabric_tariff': cotton_ready_tariff,
		'printed_fabric_tariff': cotton_printed_tariff,
	},
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
	from textile.utils import update_conversion_factor_global_defaults

	populate_stock_entry_types()
	populate_customs_tariff_number()
	populate_fabric_material()
	populate_fabric_type()
	create_printing_uom()
	update_conversion_factor_global_defaults()


def populate_stock_entry_types():
	for name, purpose in stock_entry_types:
		if not frappe.db.exists("Stock Entry Type", name):

			doc = frappe.get_doc({
				"doctype": "Stock Entry Type",
				"purpose": purpose,
			})
			doc.__newname = name
			doc.save()

	frappe.db.set_single_value("Fabric Pretreatment Settings", {
		"stock_entry_type_for_fabric_transfer": "Fabric Transfer for Pretreatment",
		"stock_entry_type_for_operation_consumption": "Pretreatment Operation",
		"stock_entry_type_for_pretreatment_prodution": "Fabric Pretreatment",
	})

	frappe.db.set_single_value("Fabric Printing Settings", {
		"stock_entry_type_for_fabric_transfer": "Fabric Transfer for Printing",
		"stock_entry_type_for_print_production": "Fabric Printing",
		"stock_entry_type_for_fabric_coating": "Fabric Coating",
	})


def populate_customs_tariff_number():
	for d in customs_tariff_numbers:
		if not frappe.db.exists("Customs Tariff Number", d['tariff_number']):
			doc = frappe.new_doc("Customs Tariff Number")
			doc.update(d)
			doc.save()


def populate_fabric_material(overwrite=False):
	for d in fabric_materials:
		exists = frappe.db.exists("Fabric Material", d['fabric_material'])

		if exists:
			if overwrite:
				doc = frappe.get_doc("Fabric Material", d['fabric_material'])
			else:
				continue
		else:
			doc = frappe.new_doc("Fabric Material")

		doc.update(d)
		doc.save()


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
