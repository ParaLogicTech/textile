
def map_print_order_reference_in_delivery_note_item(mapper):
	if not mapper.get("Delivery Note Item"):
		return

	field_map = mapper["Delivery Note Item"]["field_map"]
	field_map["print_order"] = "print_order"
	field_map["print_order_item"] = "print_order_item"
