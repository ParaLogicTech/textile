frappe.provide("textile");

frappe.pages['print-work-order'].on_page_show = function(wrapper) {
	if (!textile.print_work_order_list) {
		textile.print_work_order_list = new textile.PrintWorkOrder(wrapper);
		window.cur_list = textile.print_work_order_list.list_view;
	} else {
		if (textile.print_work_order_list?.list_view) {
			window.cur_list = textile.print_work_order_list.list_view;
			textile.print_work_order_list.list_view.show();
		}
	}
}

textile.PrintWorkOrder = class PrintWorkOrder {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Print Work Order"),
			single_column: false
		});
		this.parent = wrapper;

		this.make();
	}

	make() {
		this.list_view = new textile.PrintWorkOrderList({
			doctype: "Work Order",
			parent: this.parent,
		});
	}
}

textile.PrintWorkOrderList = class PrintWorkOrderList extends textile.PrintListView {
	get_progress_html(doc) {
		return erpnext.manufacturing.show_progress_for_production(doc);
	}

	get_details_html(doc) {
		return `
			<div class="clearfix design-properties">
				<div class="pull-left">
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
							<th>Produced:</th>
							<td>
								${this.get_formatted("produced_qty", doc)}
								/
								${this.get_formatted("qty", doc)}
								${doc.stock_uom}
								(${this.get_formatted("per_produced", doc)})
							</td>
						</tr>
					</table>
				</div>
			</div>
		`;
	}
}
