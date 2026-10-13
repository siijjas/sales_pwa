import frappe
from frappe.model.document import Document


class SalesShiftOpening(Document):
	def validate(self):
		self.opening_float = sum(
			(row.opening_amount or 0) for row in (self.balance_details or [])
		)
