// Copyright (c) 2023, ParaLogic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Textile Email Digest', {
	refresh: function(frm) {
		frm.add_custom_button(__("Send Now"), () => frm.trigger('send_now'));
		frm.add_custom_button(__("Preview"), () => frm.trigger('preview'));
	},

	send_now: function(frm) {
		frm.call({
			method: "send",
			doc: frm.doc,
			freeze: 1,
		});
	},

	preview: function(frm) {
		frm.call({
			method: "get_preview_html",
			doc: frm.doc,
			callback: (r) => {
				const fields = [{
					fieldname: "preview_html", fieldtype: "HTML", options: r.message.message
				}];

				let dialog = new frappe.ui.Dialog({
					title: r.message.subject, fields: fields, size: "medium",
				});
				dialog.show();
			}
		});
	},

	addremove_recipients: function(frm) {
		return frappe.call({
			method: "get_users",
			doc: frm.doc,
			callback: function (r) {
				if (r.message && !r.exc) {
					let dialog_html = "";
					for (let user of r.message) {
						dialog_html += `
							<div class="checkbox"><label>
								<input type="checkbox" data-id="${user.email}" ${user.checked ? 'checked' : ''}>
								<span style='${user.enabled ? '' : 'color: red'}'>${user.email} ${user.enabled ? '' : '(Disabled User)'}</span>
							</label></div>
						`;
					}

					let dialog = new frappe.ui.Dialog({
						title: __('Add/Remove Recipients'),
						width: 400,
						primary_action: function() {
							let receiver_list = [];
							for (let input of $(dialog.body).find('input:checked')) {
								receiver_list.push($(input).attr('data-id'));
							}
							frm.set_value('recipient_list', receiver_list.join('\n'));
							dialog.hide();
						},
						primary_action_label: __('Update'),
					});

					$(dialog_html).appendTo(dialog.body);
					dialog.show();
				}
			}
		});
	},
});


