frappe.provide("textile");

frappe.pages['print-order-packing'].on_page_show = function(wrapper) {
	if (!textile.print_order_packing) {
		textile.print_order_packing = new textile.PrintOrderPacking(wrapper);
		window.cur_list = textile.print_order_packing.list_view;
	} else {
		if (textile.print_order_packing?.list_view) {
			window.cur_list = textile.print_order_packing.list_view;
			textile.print_order_packing.list_view.show();
		}
	}
}

textile.PrintOrderPacking = class PrintOrderPacking {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Print Order Packing"),
			single_column: false
		});
		this.parent = wrapper;

		this.make();
	}

	make() {
		this.list_view = new textile.PrintOrderPackingList({
			doctype: "Work Order",
			parent: this.parent,
		});
	}
}

textile.PrintOrderPackingList = class PrintOrderPackingList extends textile.PrintListView {
	page_title = __("Print Order Packing")
	check_on_click = true

	setup_defaults() {
		let out = super.setup_defaults();
		this.can_create = false;
		this.can_write = false;
		this.page_length = 100;
		return out;
	}

	get_args() {
		const args = super.get_args();

		args.filters.push(["Work Order", "packing_slip_required", "=", 1]);
		args.filters.push(["Work Order", "docstatus", "=", 1]);

		args.or_filters = [
			["packing_status", "=", "To Pack"],
			["last_packing_date", "=", frappe.datetime.get_today()],
		];

		return args;
	}

	toggle_actions_menu_button() {
		this.page.hide_actions_menu();
	}

	setup_view_menu() {

	}

	get_button_html() {
		return "";
	}

	set_primary_action() {
		super.set_primary_action();
		this.page.set_primary_action(
			__("Create Packing Slip"),
			() => this.make_packing_slip(),
			"add"
		);
	}

	make_packing_slip() {
		let work_orders = this.get_checked_items(true);
		if (!work_orders || !work_orders.length) {
			frappe.throw(__("Please select designs to pack first"));
		}

		return frappe.call({
			method: "erpnext.manufacturing.doctype.work_order.work_order.make_packing_slip",
			args: {
				"work_orders": work_orders,
			},
			callback: function (r) {
				if (!r.exc) {
					var doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			}
		});
	}

	get_indicator_html(doc) {
		const indicator = frappe.get_indicator(doc, this.doctype);
		// sequence is important
		const docstatus_description = [
			__("Document is in draft state"),
			__("Document has been submitted"),
			__("Document has been cancelled"),
		];
		const title = docstatus_description[doc.docstatus || 0];
		if (indicator) {
			return `<span class="indicator-pill ${indicator[1]} filterable ellipsis"
				data-filter='${indicator[2]}' title='${title}'>
				<span class="ellipsis">${doc.docstatus == 1 ? "Production" : ""} ${__(indicator[0])}</span>
			<span>`;
		}
		return "";
	}

	get_progress_html(doc) {
		return erpnext.manufacturing.show_progress_for_packing(doc);
	}

	get_details_html(doc) {
		return `
			<div class="design-properties">
				<table>
					<tr>
						<th>Print Order:</th>
						<td>${doc.print_order || ""}</td>
					</tr>
					<tr>
						<th>Customer:</th>
						<td>${doc.customer_name || doc.customer || ""}</td>
					</tr>
					<tr>
						<th>Fabric:</th>
						<td>${doc.fabric_item_name || doc.fabric_item || ""}</td>
					</tr>
					<tr>
						<th>Packed:</th>
						<td>
							${this.get_formatted("packed_qty", doc)}
							/
							${this.get_formatted("produced_qty", doc)}
							Meter
						</td>
					</tr>
				</table>
			</div>
		`;
	}
}
