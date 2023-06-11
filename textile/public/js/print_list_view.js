frappe.provide("textile");

textile.PrintListView = class PrintListView extends frappe.views.ListView {
	hide_row_button = true;

	set_breadcrumbs() {
		frappe.breadcrumbs.add("Digital Printing", this.doctype);
	}

	get_header_html() {
		let subject_html = `
			<input class="level-item list-check-all" type="checkbox"
				title="${__("Select All")}">
			<span class="level-item">${__(this.doctype)}</span>
		`;

		return this.get_header_html_skeleton(subject_html, '<span class="list-count"></span>');
	}

	get_list_row_html(doc) {
		return this.get_list_row_html_skeleton(this.get_left_html(doc), this.get_right_html(doc));
	}

	get_list_row_html_skeleton(left = "", right = "") {
		return `
			<div class="list-row-container" tabindex="1">
				<div class="level list-row" style="height: auto; padding: 10px 15px;">
					<div class="level-left">
						${left}
					</div>
					<div class="level-right text-muted ellipsis">
						${right}
					</div>
				</div>
			</div>
		`;
	}

	get_left_html(doc) {
		return `
			<div class="list-row-col list-subject level">
				<span class="level-item select-like">
					<input class="list-row-checkbox" type="checkbox" data-name="${escape(doc.name)}">
				</span>

				<div class="clearfix" style="width: 100%">
					<div class="pull-left" style="width: 65%;">
						${this.get_subject_html(doc)}
						${this.get_progress_html(doc)}
						${this.get_details_html(doc)}
					</div>
					<div class="pull-right" style="width: 35%; padding-left: 15px;">
						${this.get_image_html(doc)}
					</div>
				</div>
			</div>
		`;
	}

	get_subject_html(doc) {
		let subject_field = this.columns[0].df;
		let value = doc[subject_field.fieldname];
		if (this.settings.formatters && this.settings.formatters[subject_field.fieldname]) {
			let formatter = this.settings.formatters[subject_field.fieldname];
			value = formatter(value, subject_field, doc);
		}
		if (!value) {
			value = doc.name;
		}
		let subject = strip_html(value.toString());
		let escaped_subject = frappe.utils.escape_html(subject);

		return `
			<div class="clearfix" title="${escaped_subject}">
				<div class="pull-left">
					<a style="font-size: 16px;"
						href="${this.get_form_link(doc)}"
						title="${escaped_subject}"
						data-doctype="${this.doctype}"
						data-name="${escaped_subject}">
						${subject}
					</a>
				</div>
				<div class="pull-right text-right">
					${this.get_indicator_html(doc)}
				</div>
			</div>
		`;
	}

	get_progress_html(doc) {
		return "";
	}

	get_details_html(doc) {
		return "";
	}

	get_image_html(doc) {
		return `<img src="/api/method/textile.utils.get_rotated_image?file=${encodeURI(doc.image)}" style="max-height: 123px;" alt="">`
	}

	get_button_html(doc) {
		let settings_button = "";
		if (this.settings.button && this.settings.button.show(doc)) {
			settings_button = `
				<button class="btn btn-action btn-md ${this.settings.button?.get_class(doc) || "btn-default"}"
					data-name="${doc.name}" data-idx="${doc._idx}"
					title="${this.settings.button.get_description(doc)}">
					${this.settings.button.get_label(doc)}
				</button>
			`;
		}

		return settings_button;
	}

	get_formatted(fieldname, doc) {
		let df = frappe.meta.get_docfield(this.doctype, fieldname);
		return frappe.format(doc[fieldname], df, {'no_newlines': 1, 'inline': true}, doc);
	}
}

textile.PrintWorkOrderList = class PrintWorkOrderList extends textile.PrintListView {
	page_title = __("Print Work Order")

	async set_fields() {
		await super.set_fields();
		this._add_field("customer");
		this._add_field("customer_name");
		this._add_field("print_order");
		this._add_field("qty");
		this._add_field("produced_qty");
		this._add_field("stock_uom");
		this._add_field("per_produced");
	}

	get_filters_for_args() {
		let filters = super.get_filters_for_args();
		const print_order_filter = filters.find((f) => f[1] == "print_order" && f[2] == "is" && f[3] == "set");
		if (!print_order_filter) {
			filters.push();
		}

		return filters;
	}

	get_args() {
		const args = super.get_args();
		args.filters.push(["Work Order", "print_order", "is", "set"]);
		return args;
	}

	get_progress_html(doc) {
		return `
			<div class="progress" style="margin-top: 5px;">
				<div class="progress-bar progress-bar-success" role="progressbar"
					aria-valuenow="${doc.per_produced}"
					aria-valuemin="0" aria-valuemax="100" style="width: ${Math.round(doc.per_produced)}%;">
				</div>
			</div>
		`;
	}

	get_details_html(doc) {
		return `
			<div class="clearfix" style="margin-top: 5px;">
				<div class="pull-left">
					<table>
						<tr>
							<th style="padding-right: 3px;">Print Order:</th>
							<td>${doc.print_order || ""}</td>
						</tr>
						<tr>
							<th style="padding-right: 3px;">Customer:</th>
							<td>${doc.customer_name || doc.customer || ""}</td>
						</tr>
						<tr>
							<th style="padding-right: 3px;">Order Qty:</th>
							<td>${this.get_formatted("qty", doc)} ${doc.stock_uom}</td>
						</tr>
						<tr>
							<th style="padding-right: 3px;">Produced:</th>
							<td>${this.get_formatted("produced_qty", doc)} ${doc.stock_uom}</td>
						</tr>
					</table>
				</div>
				<div class="pull-right text-right">
					${this.get_button_html(doc)}
				</div>
			</div>
		`;
	}
}