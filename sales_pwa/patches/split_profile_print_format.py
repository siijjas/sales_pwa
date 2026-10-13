import frappe


def execute():
	"""Sales Profile.print_format (one format for everything) became one field per
	printed document. Move each existing value to the field its format belongs to,
	so a profile that printed invoices with "JMCC POS" keeps doing so."""
	if not frappe.db.has_column("Sales Profile", "print_format"):
		return
	field_for = {"Sales Order": "order_print_format", "Sales Invoice": "invoice_print_format", "Payment Entry": "payment_print_format"}
	rows = frappe.db.sql(
		"""select name, print_format from `tabSales Profile` where ifnull(print_format, '') != ''""",
		as_dict=True,
	)
	for row in rows:
		doc_type = frappe.db.get_value("Print Format", row.print_format, "doc_type")
		field = field_for.get(doc_type)
		if field and frappe.db.has_column("Sales Profile", field):
			frappe.db.set_value("Sales Profile", row.name, field, row.print_format, update_modified=False)
	frappe.cache.delete_keys("sales_pwa:driver_config:")
