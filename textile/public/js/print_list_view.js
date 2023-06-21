frappe.provide("textile");

textile.PrintListView = class PrintListView extends frappe.views.ListView {
	hide_row_button = true;
	image_fieldname = "image"

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
			<div class="list-row-container print-list-view-row" tabindex="1">
				<div class="level list-row">
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
					${this.get_checkbox_html(doc)}
				</span>

				<div class="clearfix" style="width: 100%">
					<div class="pull-left design-details">
						${this.get_subject_html(doc)}
						${this.get_progress_html(doc)}
						${this.get_details_html(doc)}
					</div>
					<div class="pull-right design-image">
						${this.get_image_html(doc)}
					</div>
				</div>
			</div>
		`;
	}

	get_checkbox_html(doc) {
		return `<input class="list-row-checkbox" type="checkbox" data-name="${escape(doc.name)}">`;
	}

	get_subject_html(doc) {
		let subject_fieldname = this.subject_fieldname || this.columns[0].df.fieldname;
		let value = doc[subject_fieldname];

		if (!value) {
			value = doc.name;
		}
		let subject = strip_html(value.toString());
		let escaped_subject = frappe.utils.escape_html(subject);

		return `
			<div class="clearfix" title="${escaped_subject}">
				<div class="pull-left">
					<a class="design-name"
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
		return `<img src="/api/method/textile.utils.get_rotated_image?file=${encodeURIComponent(doc[this.image_fieldname])}" alt="">`
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
	async set_fields() {
		await super.set_fields();
		this._add_field("print_order");
		this._add_field("customer");
		this._add_field("customer_name");
		this._add_field("fabric_item");
		this._add_field("fabric_item_name");
		this._add_field("process_item");
		this._add_field("process_item_name");
		this._add_field("qty");
		this._add_field("produced_qty");
		this._add_field("stock_uom");
		this._add_field("per_produced");
		this._add_field("production_status");
	}

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
				<div class="pull-right text-right">
					${this.get_button_html(doc)}
				</div>
			</div>
		`;
	}
}

frappe.provide("frappe.views.custom_view_classes.Work Order");
frappe.views.custom_view_classes["Work Order"]["List"] = textile.PrintWorkOrderList;
