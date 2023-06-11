frappe.provide("textile");

frappe.pages['print-work-orders'].on_page_show = function(wrapper) {
	if (!textile.print_work_orders) {
		textile.print_work_orders = new textile.PrintWorkOrders(wrapper);
		window.cur_list = textile.print_work_orders.list_view;
	} else {
		if (textile.print_work_orders?.list_view) {
			window.cur_list = textile.print_work_orders.list_view;
			textile.print_work_orders.list_view.show();
		}
	}
}

textile.PrintWorkOrders = class PrintWorkOrders {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Print Work Orders"),
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

