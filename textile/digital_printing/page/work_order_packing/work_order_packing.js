frappe.provide("textile");

frappe.pages['work-order-packing'].on_page_show = function(wrapper) {
	if (!textile.work_order_packing) {
		textile.work_order_packing = new textile.WorkOrderPacking(wrapper);
		window.cur_list = textile.work_order_packing.list_view;
	} else {
		if (textile.work_order_packing?.list_view) {
			window.cur_list = textile.work_order_packing.list_view;
			textile.work_order_packing.list_view.show();
		}
	}
}

textile.WorkOrderPacking = class WorkOrderPacking {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Work Order Packing"),
			single_column: false
		});
		this.parent = wrapper;

		this.make();
	}

	make() {
		this.list_view = new textile.WorkOrderPackingList({
			doctype: "Work Order",
			parent: this.parent,
		});
	}
}

textile.WorkOrderPackingList = class WorkOrderPackingList extends textile.PrintListView {
	page_title = "Work Order Packing"
	check_on_click = true

	setup_defaults() {
		let out = super.setup_defaults();
		this.can_create = false;
		this.can_write = false;
		this.page_length = 100;
		return out;
	}

	async set_fields() {
		await super.set_fields();
		this._add_field("print_order");
		this._add_field("customer");
		this._add_field("customer_name");
		this._add_field("fabric_item");
		this._add_field("fabric_item_name");
		this._add_field("qty");
		this._add_field("produced_qty");
		this._add_field("packed_qty");
		this._add_field("stock_uom");
		this._add_field("per_produced");
		this._add_field("per_packed");
		this._add_field("packing_slip_required");
		this._add_field("production_status");
		this._add_field("packing_status");
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

	}

	setup_view_menu() {

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
