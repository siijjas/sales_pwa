// Desk helpers for Sales Printer: a test page, whether the agent reached it lately, and
// the list of printers on the agent's computer for the System printer choice.
frappe.ui.form.on('Sales Printer', {
	refresh(frm) {
		fill_system_printers(frm);
		if (frm.is_new()) return;
		const minutes = frm.doc.last_contact_at ? moment().diff(moment(frm.doc.last_contact_at), 'minutes') : null;
		const ok = (frm.doc.last_status || '').startsWith('Printed') || (frm.doc.last_status || '').startsWith('Reachable');
		if (minutes === null) frm.page.set_indicator(__('Not checked yet'), 'gray');
		else if (minutes <= 3 && ok) frm.page.set_indicator(__('Reachable'), 'green');
		else if (minutes <= 3) frm.page.set_indicator(__('Problem'), 'red');
		else frm.page.set_indicator(__('Agent offline'), 'orange');
		frm.add_custom_button(__('Test print'), () => {
			frm.call('test_print').then((r) => {
				const job = r.message || {};
				frappe.show_alert({ message: __('Test page queued as {0}. The agent prints it on its next poll.', [frappe.utils.escape_html(job.job || '')]), indicator: 'green' });
			});
		});
	},
	agent(frm) {
		fill_system_printers(frm);
	},
	protocol(frm) {
		if (frm.doc.protocol !== 'System printer' && !frm.doc.port) frm.set_value('port', frm.doc.protocol === 'IPP' ? 631 : 9100);
		fill_system_printers(frm);
	},
	printer_type(frm) {
		if (frm.doc.printer_type === 'Receipt (ESC/POS)' && frm.doc.protocol === 'IPP') frm.set_value('protocol', 'Raw (port 9100)');
		else if (frm.doc.printer_type === 'Document (PDF)' && frm.doc.protocol === 'Raw (port 9100)') frm.set_value('protocol', 'IPP');
	},
});

function fill_system_printers(frm) {
	if (!frm.doc.agent) return;
	frappe
		.xcall('sales_pwa.sales_app.doctype.sales_printer.sales_printer.system_printers', { agent: frm.doc.agent })
		.then((names) => {
			frm.set_df_property('system_printer', 'options', names || []);
			if (frm.doc.protocol === 'System printer' && !(names || []).length) {
				frm.set_df_property(
					'system_printer',
					'description',
					__('The agent has not reported its printers yet: start it, wait a minute, reload. Or type the name exactly as the computer shows it.')
				);
			}
		});
}
