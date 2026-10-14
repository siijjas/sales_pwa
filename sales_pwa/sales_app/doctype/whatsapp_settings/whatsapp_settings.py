import frappe
from frappe.model.document import Document

from sales_pwa.sales_app.whatsapp import validate_templates


class WhatsAppSettings(Document):
	"""Where the Sales App posts WhatsApp notifications and which events it posts.
	The sending itself lives in sales_pwa.sales_app.whatsapp."""

	def validate(self):
		self.gateway_url = (self.gateway_url or "").strip().rstrip("/")
		self.group_id = (self.group_id or "").strip()
		if self.max_items is None or self.max_items < 0:
			self.max_items = 0
		validate_templates(self)
		if not self.enabled:
			return
		if not self.gateway_url:
			frappe.throw("Gateway URL is required while notifications are enabled.")
		if not self.gateway_url.startswith(("http://", "https://")):
			frappe.throw("Gateway URL must start with http:// or https://")
		if not self.group_id:
			frappe.throw("Choose the WhatsApp group to post into, or disable notifications.")
		if "@" not in self.group_id:
			frappe.throw("Group must be a WhatsApp JID such as 120363012345678901@g.us. Use Pick group.")
