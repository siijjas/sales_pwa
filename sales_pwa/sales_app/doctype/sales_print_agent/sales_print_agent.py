import frappe
from frappe.model.document import Document


class SalesPrintAgent(Document):
	"""A machine on a shop's LAN that runs print-agent/ and feeds the printers there.

	The token is the agent's only credential: it is generated here, typed into the
	agent's .env once, and compared in constant time on every poll (printing.py).
	"""

	def before_insert(self):
		self.token = new_token()

	@frappe.whitelist()
	def regenerate_token(self):
		self.check_permission("write")
		self.token = new_token()
		self.save()
		return self.token


def new_token() -> str:
	return frappe.generate_hash(length=48)
