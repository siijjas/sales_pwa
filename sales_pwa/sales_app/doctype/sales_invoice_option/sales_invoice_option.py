import frappe
from frappe.model.document import Document


class SalesInvoiceOption(Document):
	"""A named way of raising a Sales Invoice from the app: which naming series the
	invoice takes and which tax template it is billed with. Sales Profiles pick the
	options their staff may use; the app previews the number and totals before the
	invoice is created."""

	def validate(self):
		self.naming_series = (self.naming_series or "").strip()
		if self.naming_series not in sales_invoice_naming_series():
			frappe.throw(
				f"'{self.naming_series}' is not a Sales Invoice naming series. "
				"Add it under Settings > Naming Series first."
			)
		if self.taxes_and_charges:
			template = frappe.db.get_value(
				"Sales Taxes and Charges Template", self.taxes_and_charges, ["company", "disabled"], as_dict=True
			)
			if not template:
				frappe.throw(f"Tax template {self.taxes_and_charges} does not exist")
			if template.disabled:
				frappe.throw(f"Tax template {self.taxes_and_charges} is disabled")
			if self.company and template.company and template.company != self.company:
				frappe.throw(f"Tax template {self.taxes_and_charges} belongs to {template.company}, not {self.company}")
			if not self.company:
				self.company = template.company

	def on_update(self):
		_clear_caches_of_profiles_using(self.name)

	def on_trash(self):
		_clear_caches_of_profiles_using(self.name)


def sales_invoice_naming_series() -> list[str]:
	"""The series a Sales Invoice may carry: ERPNext rejects any other value because
	naming_series is a Select."""
	return [s for s in frappe.get_meta("Sales Invoice").get_naming_series_options() if s]


def _clear_caches_of_profiles_using(option: str):
	"""Staff carry their profile's invoice options in the cached driver config; a change
	to the option master must reach them without waiting for the cache to expire."""
	from sales_pwa.sales_app.doctype.sales_profile.sales_profile import _clear_driver_caches

	profiles = frappe.get_all(
		"Sales Profile Invoice Option",
		filters={"invoice_option": option, "parenttype": "Sales Profile"},
		pluck="parent",
		distinct=True,
	)
	if not profiles:
		return
	users = frappe.get_all(
		"Sales Profile Driver",
		filters={"parent": ["in", profiles], "parenttype": "Sales Profile"},
		pluck="driver_user",
		distinct=True,
	)
	_clear_driver_caches(set(users))
