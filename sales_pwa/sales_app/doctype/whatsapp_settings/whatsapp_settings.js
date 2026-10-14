// Desk helpers for WhatsApp Settings: check the gateway, pair it, pick the group,
// send a test message, preview and reset the message templates. All calls go
// through sales_pwa.sales_app.whatsapp.
frappe.ui.form.on('WhatsApp Settings', {
	onload(frm) {
		render_template_help(frm);
	},
	refresh(frm) {
		frm.add_custom_button(__('Preview messages'), () => preview_messages(frm), __('Message text'));
		frm.add_custom_button(__('Reset message text'), () => reset_templates(frm), __('Message text'));
		const colour = { Connected: 'green', 'Not linked': 'orange', Connecting: 'orange', Down: 'red', Restricted: 'red' };
		if (frm.doc.status) frm.page.set_indicator(__(frm.doc.status), colour[frm.doc.status] || 'gray');
		frm.add_custom_button(__('Check connection'), () => check_connection(frm));
		frm.add_custom_button(__('Pair device'), () => pair_device(frm));
		frm.add_custom_button(__('Pick group'), () => pick_group(frm));
		frm.add_custom_button(__('Send test message'), () => send_test(frm));
		frm.set_intro(
			__('Save the gateway URL and API key first; the buttons above use the saved values.'),
			'blue'
		);
	},
});

function call(method, args) {
	return frappe.xcall(`sales_pwa.sales_app.whatsapp.${method}`, args || {});
}

// Everything below is rendered as HTML by msgprint, show_alert, Dialog and Select
// (and __() substitutes its arguments verbatim), so every value that came from the
// gateway or from WhatsApp (profile names, group subjects, error text) is escaped first.
const esc = (v) => frappe.utils.escape_html(String(v == null ? '' : v));
const is_png = (v) => typeof v === 'string' && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(v);

function describe(status) {
	if (status.connected) {
		const who = status.user ? `${status.user.name || ''} ${status.user.id || ''}`.trim() : '';
		return __('Connected as {0}. {1} message(s) sent since the gateway started.', [esc(who), cint(status.sent)]);
	}
	if (status.pairing_code) return __('Not paired. Pairing code: {0}', [esc(status.pairing_code)]);
	if (status.qr_pending) return __('Not paired yet: use Pair device to scan the QR.');
	if (status.state === 'logged_out') return __('The phone unlinked this device. Use Pair device to link it again.');
	if (status.state === 'restricted') return __('WhatsApp refused this number. {0}', [esc(status.last_error)]);
	return __('Gateway reachable but WhatsApp is not connected ({0}). {1}', [esc(status.state), esc(status.last_error)]);
}

async function check_connection(frm) {
	if (frm.is_dirty()) return frappe.msgprint(__('Save the settings first.'));
	try {
		const status = await call('get_gateway_status');
		frappe.msgprint({ title: __('WhatsApp gateway'), indicator: status.connected ? 'green' : 'orange', message: describe(status) });
	} catch (e) {
		// frappe.xcall already showed the server's error message
	}
}

async function pair_device(frm) {
	if (frm.is_dirty()) return frappe.msgprint(__('Save the settings first.'));
	const d = new frappe.ui.Dialog({
		title: __('Pair WhatsApp'),
		fields: [{ fieldtype: 'HTML', fieldname: 'body' }],
	});
	let timer = null;
	const render = (html) => d.fields_dict.body.$wrapper.html(html);
	const tick = async () => {
		try {
			const s = await call('get_gateway_status');
			if (s.connected) {
				render(`<p>${describe(s)}</p>`);
				clearInterval(timer);
			} else if (s.pairing_code) {
				render(`<p>${__('WhatsApp › Linked devices › Link with phone number')}</p><h2 style="letter-spacing:3px">${esc(s.pairing_code)}</h2>`);
			} else if (is_png(s.qr)) {
				render(`<p>${__('WhatsApp › Linked devices › Link a device, then scan:')}</p><img src="${s.qr}" style="width:280px;height:280px;display:block;margin:8px auto;border-radius:8px">`);
			} else {
				render(`<p>${esc(s.last_error || __('Connecting…'))}</p>`);
			}
		} catch (e) {
			render(`<p>${__('Gateway unreachable.')}</p>`);
			clearInterval(timer);
		}
	};
	d.onhide = () => clearInterval(timer);
	d.show();
	render(`<p>${__('Loading…')}</p>`);
	tick();
	timer = setInterval(tick, 5000);
}

async function pick_group(frm) {
	if (frm.is_dirty()) return frappe.msgprint(__('Save the settings first.'));
	let groups;
	try {
		groups = await call('get_groups');
	} catch (e) {
		return;
	}
	if (!groups.length) return frappe.msgprint(__('The paired number is not a member of any group yet.'));
	const d = new frappe.ui.Dialog({
		title: __('Pick the group to post into'),
		fields: [
			{
				fieldtype: 'Select',
				fieldname: 'group',
				label: __('Group'),
				reqd: 1,
				// Select renders labels with .html(); a group subject is set by any admin of that group.
				options: groups.map((g) => ({ value: g.id, label: `${esc(g.subject)} (${cint(g.participants)})` })),
			},
		],
		primary_action_label: __('Use this group'),
		primary_action(values) {
			const chosen = groups.find((g) => g.id === values.group);
			frm.set_value('group_id', chosen.id);
			frm.set_value('group_name', chosen.subject);
			d.hide();
			frm.save();
		},
	});
	d.show();
}

async function send_test(frm) {
	if (frm.is_dirty()) return frappe.msgprint(__('Save the settings first.'));
	try {
		await call('send_test_message');
		frappe.show_alert({ message: __('Test message sent to {0}', [esc(frm.doc.group_name || frm.doc.group_id)]), indicator: 'green' });
	} catch (e) {
		// error already shown
	}
}

// --------------------------------------------------------------- templates

async function render_template_help(frm) {
	let help;
	try {
		help = await call('get_template_help');
	} catch (e) {
		return;
	}
	for (const [field, rows] of Object.entries(help)) {
		const items = rows
			.map(([name, text]) => `<li><code>{{ ${esc(name)} }}</code> — ${esc(text)}</li>`)
			.join('');
		frm.fields_dict[`${field}_help`].$wrapper.html(
			`<details><summary class="text-muted" style="cursor:pointer">${__('Variables')}</summary><ul class="small" style="padding-left:1.2em;margin-top:6px">${items}</ul></details>`
		);
	}
}

async function preview_messages(frm) {
	let out;
	try {
		out = await call('preview_messages', {
			order_template: frm.doc.order_template || '',
			payment_template: frm.doc.payment_template || '',
		});
	} catch (e) {
		return;
	}
	const bubble = (title, text) =>
		`<p class="text-muted small" style="margin:12px 0 4px">${title}</p>` +
		`<pre style="white-space:pre-wrap;background:var(--bg-light-gray);border-radius:8px;padding:10px 12px;font-family:inherit">${esc(text)}</pre>`;
	frappe.msgprint({
		title: __('Message preview'),
		message: bubble(__('Order'), out.order_template) + bubble(__('Payment'), out.payment_template),
	});
}

async function reset_templates(frm) {
	let defaults;
	try {
		defaults = await call('get_default_templates');
	} catch (e) {
		return;
	}
	for (const [field, text] of Object.entries(defaults)) frm.set_value(field, text);
	frappe.show_alert({ message: __('Built-in text loaded. Edit it and save, or clear a field to keep using the built-in text.'), indicator: 'blue' });
}
