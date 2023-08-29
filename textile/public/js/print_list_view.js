frappe.provide("textile");

textile.PrintListView = class PrintListView extends frappe.views.ListView {
	page_title = __("Print Work Order")
	hide_row_button = true;
	image_fieldname = "image"

	set_breadcrumbs() {
		frappe.breadcrumbs.add("Fabric Printing", this.doctype);
	}

	setup_defaults() {
		let out = super.setup_defaults();

		this.sort_by = "print_order";
		this.sort_order = "desc";

		return out;
	}

	get_args() {
		const args = super.get_args();
		args.filters.push(["Work Order", "print_order", "is", "set"]);
		return args;
	}

	setup_sort_selector() {
		super.setup_sort_selector();
		if (this.sort_selector) {
			this.sort_selector.get_sql_string = function() {
				var sql = '`tab' + this.doctype + '`.`' + this.sort_by + '` ' +  this.sort_order

				if (this.sort_by !== 'print_order') {
					sql += ', `tab' + this.doctype + '`.`print_order` ' +  this.sort_order
				}

				sql += ', `tab' + this.doctype + '`.`order_line_no` asc'

				return sql;
			}
		}
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
						${this.get_details_html(doc)}
						${this.get_progress_html(doc)}
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
		let subject = this.get_subject(doc);
		let escaped_subject = frappe.utils.escape_html(subject);

		return `
			<div class="d-flex justify-content-between align-items-center flex-wrap" title="${escaped_subject}">
				<div class="d-flex">
					<a class="design-name"
						href="${this.get_form_link(doc)}"
						title="${escaped_subject}"
						data-doctype="${this.doctype}"
						data-name="${escaped_subject}">
						${subject}
					</a>
				</div>
				<div class="d-flex">
					<div>
						${this.get_indicator_html(doc)}
					</div>
					<div class="ml-2">
						${this.get_button_html(doc)}
					</div>
				</div>
			</div>
		`;
	}

	get_subject(doc) {
		let subject_fieldname = this.subject_fieldname || this.columns[0].df.fieldname;
		let subject = doc[subject_fieldname];

		if (!subject) {
			subject = doc.name;
		}
		subject = strip_html(subject.toString());

		if (doc.order_line_no) {
			subject = `(${doc.order_line_no}) ${subject}`;
		}

		return subject;
	}

	get_progress_html(doc) {
		return "";
	}

	get_details_html(doc) {
		return "";
	}

	get_image_html(doc) {
		if (doc[this.image_fieldname]) {
			return `<img src="/api/method/textile.utils.get_rotated_image?file=${encodeURIComponent(doc[this.image_fieldname])}" alt="${escape(doc.item_name)}">`;
		} else {
			return "";
		}
	}

	get_button_html(doc) {
		let settings_button = "";
		if (this.settings.button && this.settings.button.show(doc)) {
			settings_button = `
				<button class="btn btn-action btn-sm ${this.settings.button?.get_class(doc) || "btn-default"}"
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
