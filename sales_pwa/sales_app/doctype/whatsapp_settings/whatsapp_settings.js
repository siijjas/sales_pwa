// Desk helpers for WhatsApp Settings: check the gateway, pair it, pick the group,
// and send a test message. All calls go through sales_pwa.sales_app.whatsapp.
frappe.ui.form.on('WhatsApp Settings', {
	refresh(frm) {
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

function describe(status) {
	if (status.connected) {
		const who = status.user ? `${status.user.name || ''} ${status.user.id || ''}`.trim() : '';
		return __('Connected as {0}. {1} message(s) sent since the gateway started.', [who, status.sent || 0]);
	}
	if (status.pairing_code) return __('Not paired. Pairing code: {0}', [status.pairing_code]);
	if (status.qr_pending) return __('Not paired yet: use Pair device to scan the QR.');
	return __('Gateway reachable but WhatsApp is not connected. {0}', [status.last_error || '']);
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
				render(`<p>${__('WhatsApp › Linked devices › Link with phone number')}</p><h2 style="letter-spacing:3px">${s.pairing_code}</h2>`);
			} else if (s.qr) {
				render(`<p>${__('WhatsApp › Linked devices › Link a device, then scan:')}</p><img src="${s.qr}" style="width:280px;height:280px;display:block;margin:8px auto;border-radius:8px">`);
			} else {
				render(`<p>${frappe.utils.escape_html(s.last_error || __('Connecting…'))}</p>`);
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
				options: groups.map((g) => ({ value: g.id, label: `${g.subject} (${g.participants})` })),
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
		frappe.show_alert({ message: __('Test message sent to {0}', [frm.doc.group_name || frm.doc.group_id]), indicator: 'green' });
	} catch (e) {
		// error already shown
	}
}
