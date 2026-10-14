// Desk helpers for Sales Print Agent: a fresh token, and the agent's state at a glance.
frappe.ui.form.on('Sales Print Agent', {
	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(__('Save to generate the agent token.'), 'blue');
			return;
		}
		const minutes = frm.doc.last_contact_at ? moment().diff(moment(frm.doc.last_contact_at), 'minutes') : null;
		if (minutes === null) frm.page.set_indicator(__('Never connected'), 'gray');
		else if (minutes <= 3) frm.page.set_indicator(__('Online'), 'green');
		else frm.page.set_indicator(__('Offline'), 'red');
		frm.add_custom_button(__('Regenerate token'), () => {
			frappe.confirm(__('The agent stops printing until its .env carries the new token. Continue?'), () => {
				frm.call('regenerate_token').then(() => frm.reload_doc());
			});
		});
		frm.set_intro(
			__('Run print-agent/ on a computer on the printers\' LAN with SP_SERVER_URL={0} and SP_AGENT_TOKEN set to the token below. See print-agent/README.md.', [
				frappe.utils.escape_html(frappe.urllib.get_base_url()),
			]),
			'blue'
		);
	},
});
