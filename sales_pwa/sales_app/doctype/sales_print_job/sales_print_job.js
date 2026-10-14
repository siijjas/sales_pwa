frappe.ui.form.on('Sales Print Job', {
	refresh(frm) {
		const colour = { Queued: 'orange', Sent: 'blue', Printed: 'green', Failed: 'red' };
		frm.page.set_indicator(__(frm.doc.status), colour[frm.doc.status] || 'gray');
		if (frm.doc.status === 'Failed' || frm.doc.status === 'Printed') {
			frm.add_custom_button(__('Print again'), () => frm.call('retry').then(() => frm.reload_doc()));
		}
	},
});
