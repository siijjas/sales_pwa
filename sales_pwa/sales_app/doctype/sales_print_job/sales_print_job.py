import frappe
from frappe.model.document import Document


class SalesPrintJob(Document):
	"""One document rendered for one printer, waiting for the printer's agent.

	Created only by printing.py (there is no create permission in the desk);
	managers can read, retry and delete jobs there.
	"""

	@frappe.whitelist()
	def retry(self):
		self.check_permission("write")
		from sales_pwa.sales_app.printing import retry

		retry(self.name)
