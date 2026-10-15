"""Tests for direct printing (sales_pwa.sales_app.printing): the ESC/POS raster
encoder, printer resolution from the Sales Profile, the job queue and the agent's
endpoints. wkhtmltoimage is not run; the bitmap is given.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_printing
"""

import base64
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from sales_pwa.sales_app import printing
from sales_pwa.sales_app.pdf import allowed_print_formats, authorize_print
from sales_pwa.sales_app.utils import _driver_cache_key

PREFIX = "_Test Print"


def _png(width: int, height: int, ink_rows: tuple[int, ...] = ()) -> bytes:
	"""A white PNG with full-width black rows at `ink_rows`."""
	import io

	from PIL import Image

	image = Image.new("L", (width, height), 255)
	for row in ink_rows:
		for x in range(width):
			image.putpixel((x, row), 0)
	out = io.BytesIO()
	image.save(out, "PNG")
	return out.getvalue()


class TestEscPos(FrappeTestCase):
	def test_raster_is_trimmed_packed_and_one_means_ink(self):
		raster, rows = printing.png_to_raster(_png(16, 10, ink_rows=(0, 3)), 16)
		self.assertEqual(rows, 4)  # blank paper below the last ink row is dropped
		self.assertEqual(len(raster), 4 * 2)
		self.assertEqual(raster[0:2], b"\xff\xff")
		self.assertEqual(raster[2:4], b"\x00\x00")
		self.assertEqual(raster[6:8], b"\xff\xff")

	def test_wide_image_is_fitted_to_the_paper(self):
		raster, rows = printing.png_to_raster(_png(64, 8, ink_rows=(0,)), 16)
		self.assertEqual(rows, 1)
		self.assertEqual(len(raster), 2)

	def test_escpos_wraps_bands_feed_cut_and_drawer(self):
		raster = bytes([0xFF, 0x00] * 3)  # 16 dots wide, 3 rows
		out = printing.escpos_receipt(raster, 3, 16, cut=True, drawer=True, band_rows=2)
		self.assertTrue(out.startswith(b"\x1b@\x1ba\x00"))
		# Two bands: 2 rows then 1 row, each GS v 0 with xL xH yL yH.
		self.assertIn(b"\x1dv0\x00\x02\x00\x02\x00" + bytes([0xFF, 0x00, 0xFF, 0x00]), out)
		self.assertIn(b"\x1dv0\x00\x02\x00\x01\x00" + bytes([0xFF, 0x00]), out)
		self.assertTrue(out.endswith(b"\x1bd\x03\x1dV\x42\x00\x1bp\x00\x19\xfa"))
		plain = printing.escpos_receipt(raster, 3, 16, cut=False, drawer=False)
		self.assertTrue(plain.endswith(b"\x1bd\x03"))
		self.assertNotIn(b"\x1dV", plain)

	def test_runaway_receipt_is_refused(self):
		with patch.object(printing, "MAX_RECEIPT_ROWS", 4):
			self.assertRaises(frappe.ValidationError, printing.png_to_raster, _png(8, 10, ink_rows=(9,)), 8)


class TestPrintingFlow(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from sales_pwa.sales_app.tests import test_shift_and_access as base

		cls.base = base.TestShiftAndAccessRegressions
		cls.base.setUpClass()
		cls.driver_user = cls.base.driver_user
		cls.van_profile = cls.base.van_profile
		cls.customer = cls.base.customer_allowed
		cls.item_code = cls.base.item_code

	def setUp(self):
		frappe.set_user("Administrator")
		self.agent = frappe.get_doc({"doctype": "Sales Print Agent", "agent_name": f"{PREFIX} Agent"}).insert()
		self.receipt = frappe.get_doc(
			{"doctype": "Sales Printer", "printer_name": f"{PREFIX} Epson", "printer_type": printing.RECEIPT, "agent": self.agent.name, "host": "192.168.1.50", "paper_width": "80"}
		).insert()
		self.office = frappe.get_doc(
			{"doctype": "Sales Printer", "printer_name": f"{PREFIX} Brother", "printer_type": printing.DOCUMENT, "protocol": "IPP", "agent": self.agent.name, "host": "192.168.1.51"}
		).insert()
		self._profile_before = frappe.db.get_value("Sales Profile", self.van_profile, list(printing.PRINTER_FIELD_OF.values()) + ["return_printer"], as_dict=True)
		self.addCleanup(self._cleanup)

	def _cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Sales Profile", self.van_profile, dict(self._profile_before))
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		frappe.db.delete("Sales Print Job", {"printer": ("in", [self.receipt.name, self.office.name])})
		for name in (self.receipt.name, self.office.name):
			frappe.delete_doc("Sales Printer", name, force=True)
		frappe.delete_doc("Sales Print Agent", self.agent.name, force=True)

	def _route(self, **fields):
		frappe.set_user("Administrator")
		frappe.db.set_value("Sales Profile", self.van_profile, fields)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))

	def _order(self):
		from sales_pwa.sales_app.sales import create_sales_order

		frappe.set_user(self.driver_user)
		result = create_sales_order(self.customer, [{"item_code": self.item_code, "qty": 1, "rate": 10}])
		return result["name"] if isinstance(result, dict) else result.name

	def _fake_render(self):
		"""Rendering is wkhtmltopdf / wkhtmltoimage work and commits nothing we want: stub it."""
		patches = [
			patch.object(printing, "render_html", return_value=("<html></html>", "Standard")),
			patch.object(printing, "html_to_png", return_value=_png(576, 4, ink_rows=(1,))),
			patch.object(printing, "render_pdf", return_value=b"%PDF-1.4 test"),
		]
		for p in patches:
			p.start()
			self.addCleanup(p.stop)

	# ------------------------------------------------------------ setup rules

	def test_printer_defaults_and_rules(self):
		self.assertEqual(self.receipt.port, 9100)
		self.assertEqual(self.office.port, 631)
		self.assertEqual(self.office.ipp_path, "/ipp/print")
		self.assertTrue(self.agent.token and len(self.agent.token) >= 40)
		bad = frappe.get_doc({"doctype": "Sales Printer", "printer_name": f"{PREFIX} Bad", "printer_type": printing.RECEIPT, "protocol": "IPP", "agent": self.agent.name, "host": "1.2.3.4"})
		self.assertRaises(frappe.ValidationError, bad.insert)
		bad.protocol = "Raw (port 9100)"
		bad.host = "1.2.3.4 /x"
		self.assertRaises(frappe.ValidationError, bad.insert)

	def test_system_printer_needs_a_queue_name_not_an_address(self):
		usb = frappe.get_doc({"doctype": "Sales Printer", "printer_name": f"{PREFIX} USB", "printer_type": printing.RECEIPT, "protocol": "System printer", "agent": self.agent.name, "system_printer": " EPSON TM-T20III Receipt "})
		self.addCleanup(lambda: frappe.delete_doc("Sales Printer", usb.name, force=True, ignore_permissions=True))
		usb.insert()
		self.assertEqual((usb.system_printer, usb.host, usb.port), ("EPSON TM-T20III Receipt", "", 0))
		blank = frappe.get_doc({"doctype": "Sales Printer", "printer_name": f"{PREFIX} Blank", "printer_type": printing.DOCUMENT, "protocol": "System printer", "agent": self.agent.name})
		self.assertRaises(frappe.ValidationError, blank.insert)
		# The agent's poll gets the queue name, and its reported printer list is kept for the picker.
		self._as_agent(self.agent.token)
		frappe.form_dict.update({"system_printers": ["EPSON TM-T20III Receipt", "Brother HL-L2350DW series", 7, ""]})
		reply = printing.agent_poll()
		row = next(p for p in reply["printers"] if p["id"] == usb.name)
		self.assertEqual((row["protocol"], row["system_printer"]), ("system", "EPSON TM-T20III Receipt"))
		frappe.set_user("Administrator")
		from sales_pwa.sales_app.doctype.sales_printer.sales_printer import system_printers

		self.assertEqual(system_printers(self.agent.name), ["EPSON TM-T20III Receipt", "Brother HL-L2350DW series", "7"])

	def test_profile_refuses_unknown_printer(self):
		doc = frappe.get_doc("Sales Profile", self.van_profile)
		doc.order_printer = "No Such Printer"
		self.assertRaises(frappe.ValidationError, doc.validate)

	# ------------------------------------------------------------ resolution

	def test_no_printer_means_pdf(self):
		self._route(order_printer=None)
		order = self._order()
		self._fake_render()
		self.assertEqual(printing.print_document("Sales Order", order), {"job": None})

	def test_order_goes_to_the_profiles_printer_as_escpos(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		result = printing.print_document("Sales Order", order)
		self.assertEqual(result["printer"], self.receipt.name)
		self.assertEqual(result["printer_type"], printing.RECEIPT)
		self.assertFalse(result["online"])  # the agent has never polled
		job = frappe.get_doc("Sales Print Job", result["job"])
		self.assertEqual((job.status, job.payload_type, job.ref_doctype, job.ref_name, job.requested_by), ("Queued", "escpos", "Sales Order", order, self.driver_user))
		data = base64.b64decode(job.content)
		self.assertTrue(data.startswith(b"\x1b@"))
		self.assertIn(b"\x1dv0\x00\x48\x00\x02\x00", data)  # 576 dots = 72 bytes a row, 2 rows kept
		self.assertEqual(job.label, f"Sales Order {order}")

	def test_document_printer_gets_the_pdf(self):
		self._route(order_printer=self.office.name)
		order = self._order()
		self._fake_render()
		result = printing.print_document("Sales Order", order)
		job = frappe.get_doc("Sales Print Job", result["job"])
		self.assertEqual(job.payload_type, "pdf")
		self.assertEqual(base64.b64decode(job.content), b"%PDF-1.4 test")

	def test_inactive_printer_or_agent_falls_back_to_pdf(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		frappe.db.set_value("Sales Print Agent", self.agent.name, "is_active", 0)
		self.assertEqual(printing.print_document("Sales Order", order), {"job": None})
		frappe.db.set_value("Sales Print Agent", self.agent.name, "is_active", 1)
		frappe.db.set_value("Sales Printer", self.receipt.name, "is_active", 0)
		self.assertEqual(printing.print_document("Sales Order", order), {"job": None})

	def test_credit_note_prefers_the_return_printer(self):
		self._route(invoice_printer=self.office.name, return_printer=self.receipt.name)
		frappe.set_user(self.driver_user)
		invoice = frappe._dict(doctype="Sales Invoice", is_return=1, owner=self.driver_user)
		self.assertEqual(printing.resolve_printer(invoice).name, self.receipt.name)
		invoice.is_return = 0
		self.assertEqual(printing.resolve_printer(invoice).name, self.office.name)
		self._route(return_printer=None)
		invoice.is_return = 1
		self.assertEqual(printing.resolve_printer(invoice).name, self.office.name)

	def test_print_choices_offer_formats_and_live_printers(self):
		self._route(invoice_printer=self.office.name, shift_report_printer=None)
		frappe.set_user(self.driver_user)
		choices = printing.print_choices("Sales Invoice")
		names = [f["name"] for f in choices["formats"]]
		self.assertEqual(names[0], "Standard")
		self.assertIn(choices["default_format"], names)
		self.assertEqual(choices["default_printer"], self.office.name)
		by_name = {p["name"]: p for p in choices["printers"]}
		self.assertEqual(by_name[self.receipt.name]["printer_type"], printing.RECEIPT)
		self.assertFalse(by_name[self.office.name]["online"])
		self.assertIsNone(printing.print_choices("Sales Shift Opening")["default_printer"])
		# A printer whose agent is off is not offered.
		frappe.db.set_value("Sales Print Agent", self.agent.name, "is_active", 0)
		self.assertEqual(printing.print_choices("Sales Invoice")["printers"], [])
		self.assertRaises(frappe.PermissionError, printing.print_choices, "Purchase Order")

	def _print_format(self, name, doctype):
		frappe.set_user("Administrator")
		doc = frappe.get_doc(
			{"doctype": "Print Format", "name": name, "doc_type": doctype, "standard": "No", "custom_format": 1, "print_format_type": "Jinja", "html": "<p>{{ doc.name }}</p>"}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", doc.name, force=True)
		return doc.name

	def _allow_formats(self, *names):
		frappe.set_user("Administrator")
		for name in names:
			frappe.get_doc(
				{"doctype": "Sales Profile Print Format", "parent": self.van_profile, "parenttype": "Sales Profile", "parentfield": "allowed_print_formats", "print_format": name}
			).db_insert()
		self.addCleanup(frappe.db.delete, "Sales Profile Print Format", {"parent": self.van_profile})
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))

	def test_profile_limits_the_formats_staff_may_print_with(self):
		listed = self._print_format(f"{PREFIX} SO Slip", "Sales Order")
		own = self._print_format(f"{PREFIX} SO Full", "Sales Order")
		self._print_format(f"{PREFIX} SO Other", "Sales Order")
		self._route(order_print_format=own)
		self._allow_formats(listed)
		order = self._order()
		frappe.set_user(self.driver_user)
		choices = printing.print_choices("Sales Order")
		# The listed format and the profile's own one; no Standard, nothing else.
		self.assertEqual([f["name"] for f in choices["formats"]], sorted([listed, own]))
		self.assertEqual(choices["default_format"], own)
		# Nothing listed for invoices: every enabled format, Standard first.
		self.assertEqual(printing.print_choices("Sales Invoice")["formats"][0]["name"], "Standard")
		self.assertEqual(authorize_print("Sales Order", order, listed).name, order)
		for refused in ("Standard", f"{PREFIX} SO Other"):
			self.assertRaises(frappe.PermissionError, authorize_print, "Sales Order", order, refused)
		self.assertRaises(frappe.PermissionError, printing.print_document, "Sales Order", order, "Standard", self.office.name)
		# Managers without a profile are not limited.
		frappe.set_user("Administrator")
		self.assertIsNone(allowed_print_formats("Sales Order"))

	def test_a_chosen_printer_wins_over_the_profile(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		result = printing.print_document("Sales Order", order, printer=self.office.name)
		self.assertEqual(result["printer"], self.office.name)
		self.assertEqual(frappe.get_doc("Sales Print Job", result["job"]).payload_type, "pdf")
		# Blank means the profile decides, as before.
		self.assertEqual(printing.print_document("Sales Order", order, printer="")["printer"], self.receipt.name)
		# A printer that cannot print now is refused rather than silently swapped.
		frappe.db.set_value("Sales Printer", self.office.name, "is_active", 0)
		self.assertRaises(frappe.ValidationError, printing.print_document, "Sales Order", order, None, self.office.name)

	def test_shift_reports_use_the_shift_printer(self):
		self._route(shift_report_printer=self.receipt.name)
		frappe.set_user(self.driver_user)
		self.assertEqual(printing.resolve_printer(frappe._dict(doctype="Sales Shift Closing", owner=self.driver_user)).name, self.receipt.name)

	# ------------------------------------------------------------ the agent

	def _as_agent(self, token):
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(headers={printing.TOKEN_HEADER: token}, method="POST", path="/api/method/x")
		frappe.form_dict = frappe._dict()

	def test_agent_poll_hands_over_its_jobs_and_records_outcomes(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]

		self._as_agent("nonsense")
		self.assertRaises(frappe.AuthenticationError, printing.agent_poll)

		self._as_agent(self.agent.token)
		frappe.form_dict.update({"version": "1.0.0", "host": "shop-pc", "printers": {self.receipt.name: {"ok": True}, self.office.name: {"ok": False, "message": "no answer"}}})
		reply = printing.agent_poll()
		self.assertEqual(reply["agent"], self.agent.name)
		self.assertEqual({p["id"]: (p["type"], p["protocol"], p["port"]) for p in reply["printers"]}, {self.receipt.name: ("escpos", "raw", 9100), self.office.name: ("pdf", "ipp", 631)})
		self.assertEqual([j["id"] for j in reply["jobs"]], [job])
		self.assertEqual(reply["jobs"][0]["payload"], "escpos")
		self.assertTrue(base64.b64decode(reply["jobs"][0]["data"]).startswith(b"\x1b@"))
		self.assertEqual(frappe.db.get_value("Sales Print Job", job, ["status", "attempts"]), ("Sent", 1))
		self.assertEqual(frappe.db.get_value("Sales Print Agent", self.agent.name, ["agent_host", "agent_version"]), ("shop-pc", "1.0.0"))
		self.assertEqual(frappe.db.get_value("Sales Printer", self.receipt.name, "last_status"), "Reachable")
		self.assertEqual(frappe.db.get_value("Sales Printer", self.office.name, "last_status"), "Unreachable: no answer")
		# Handed over: a second poll has nothing.
		self.assertEqual(printing.agent_poll()["jobs"], [])

		frappe.form_dict = frappe._dict()
		self.assertEqual(printing.agent_report(job, ok=1), {"ok": True})
		self.assertEqual(frappe.db.get_value("Sales Print Job", job, "status"), "Printed")
		self.assertEqual(frappe.db.get_value("Sales Printer", self.receipt.name, "last_status"), f"Printed Sales Order {order}")

		# The job's requester now sees it printed; the agent is online for the staff screen.
		frappe.set_user(self.driver_user)
		self.assertEqual(printing.job_status(job)["status"], "Printed")
		frappe.set_user("Administrator")
		row = next(r for r in printing.printer_status() if r["name"] == self.receipt.name)
		self.assertTrue(row["agent_online"])

	def test_agent_only_sees_and_finishes_its_own_jobs(self):
		other = frappe.get_doc({"doctype": "Sales Print Agent", "agent_name": f"{PREFIX} Other"}).insert()
		self.addCleanup(lambda: frappe.delete_doc("Sales Print Agent", other.name, force=True, ignore_permissions=True))
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]
		self._as_agent(other.token)
		self.assertEqual(printing.agent_poll()["jobs"], [])
		self.assertEqual(printing.agent_report(job, ok=1), {"ok": False})
		self.assertEqual(frappe.db.get_value("Sales Print Job", job, "status"), "Queued")

	def test_unanswered_jobs_are_offered_again_then_fail(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]
		self._as_agent(self.agent.token)
		for attempt in range(1, printing.MAX_ATTEMPTS + 1):
			self.assertEqual([j["id"] for j in printing.agent_poll()["jobs"]], [job], f"attempt {attempt}")
			self.assertEqual(frappe.db.get_value("Sales Print Job", job, "attempts"), attempt)
			frappe.db.set_value("Sales Print Job", job, "sent_at", now_datetime() - printing.SENT_TIMEOUT - timedelta(seconds=1))
		self.assertEqual(printing.agent_poll()["jobs"], [])
		self.assertEqual(frappe.db.get_value("Sales Print Job", job, ["status", "error"]), ("Failed", "No answer from the print agent."))
		frappe.set_user("Administrator")
		printing.retry(job)
		self.assertEqual(frappe.db.get_value("Sales Print Job", job, ["status", "attempts"]), ("Queued", 0))

	def test_failed_report_keeps_the_error_for_the_phone(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]
		self._as_agent(self.agent.token)
		printing.agent_poll()
		printing.agent_report(job, ok=0, error="192.168.1.50:9100: EHOSTUNREACH")
		frappe.set_user(self.driver_user)
		status = printing.job_status(job)
		self.assertEqual((status["status"], status["error"]), ("Failed", "192.168.1.50:9100: EHOSTUNREACH"))

	def test_only_the_requester_or_a_manager_reads_a_job(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]
		frappe.set_user("Guest")
		self.assertRaises(frappe.DoesNotExistError, printing.job_status, job)

	def test_test_page_is_for_managers(self):
		self._fake_render()
		frappe.set_user(self.driver_user)
		self.assertRaises(frappe.PermissionError, printing.test_printer, self.receipt.name)
		frappe.set_user("Administrator")
		result = printing.test_printer(self.office.name)
		self.assertEqual(frappe.db.get_value("Sales Print Job", result["job"], ["label", "payload_type"]), ("Test page", "pdf"))

	def test_old_jobs_are_purged(self):
		self._route(order_printer=self.receipt.name)
		order = self._order()
		self._fake_render()
		job = printing.print_document("Sales Order", order)["job"]
		frappe.db.set_value("Sales Print Job", job, "creation", now_datetime() - printing.KEEP_JOBS - timedelta(days=1))
		self.assertGreaterEqual(printing.purge_old_jobs(), 1)
		self.assertFalse(frappe.db.exists("Sales Print Job", job))
