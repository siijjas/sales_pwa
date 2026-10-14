import frappe
from frappe.model.document import Document

RECEIPT = "Receipt (ESC/POS)"
DOCUMENT = "Document (PDF)"
RAW = "Raw (port 9100)"
IPP = "IPP"
SYSTEM = "System printer"
DEFAULT_PORTS = {RAW: 9100, IPP: 631}


class SalesPrinter(Document):
	"""A printer reached through a Sales Print Agent (printing.py): over the LAN by
	address (Raw or IPP), or as a printer installed on the agent's own computer."""

	def validate(self):
		self.host = (self.host or "").strip()
		self.system_printer = (self.system_printer or "").strip()
		if self.protocol == SYSTEM:
			if not self.system_printer:
				frappe.throw("Name the printer as the agent's computer lists it.")
			self.host = ""
			self.port = 0
			self.ipp_path = ""
		else:
			if not self.host or any(c.isspace() for c in self.host) or "/" in self.host:
				frappe.throw("IP Address or Hostname must be a single address such as 192.168.1.50.")
			if not self.port:
				self.port = DEFAULT_PORTS[self.protocol]
			if not 1 <= int(self.port) <= 65535:
				frappe.throw("Port must be between 1 and 65535.")
			self.system_printer = ""
		if self.protocol == IPP:
			self.ipp_path = "/" + (self.ipp_path or "/ipp/print").strip().lstrip("/")
		if self.printer_type == RECEIPT and self.protocol == IPP:
			frappe.throw("A receipt printer takes Raw (port 9100) or System printer, not IPP.")
		if self.printer_type == RECEIPT:
			self.scale = max(25, min(int(self.scale or 100), 400))
		if not frappe.db.get_value("Sales Print Agent", self.agent, "is_active"):
			frappe.msgprint(f"Print agent {self.agent} is inactive: nothing prints on this printer until it is active.", alert=True)

	@frappe.whitelist()
	def test_print(self):
		self.check_permission("write")
		from sales_pwa.sales_app.printing import test_print

		return test_print(self.name)


@frappe.whitelist()
def system_printers(agent: str) -> list[str]:
	"""The printers the agent's computer reported, for the System printer picker."""
	frappe.has_permission("Sales Printer", "write", throw=True)
	raw = frappe.db.get_value("Sales Print Agent", agent, "system_printers") if agent else None
	names = frappe.parse_json(raw) if raw else []
	return [str(n) for n in names] if isinstance(names, list) else []
