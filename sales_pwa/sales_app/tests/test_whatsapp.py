"""Tests for the WhatsApp notifier: settings validation, message text, event
collapsing, and the Sales-App-only filter. No gateway is contacted.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_whatsapp
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from sales_pwa.sales_app import whatsapp
from sales_pwa.sales_app.whatsapp import SETTINGS, apply_health, build_message, check_gateway_health, on_document_event

APP_PATH = "/api/method/sales_pwa.sales_app.sales.create_sales_order"


def _set_settings(**values):
	for field, value in values.items():
		frappe.db.set_single_value(SETTINGS, field, value)
	frappe.clear_document_cache(SETTINGS, SETTINGS)


class TestWhatsApp(FrappeTestCase):
	def setUp(self):
		self._request = getattr(frappe.local, "request", None)
		frappe.local.sales_pwa_whatsapp_pending = {}
		frappe.db.after_commit.reset()
		_set_settings(
			enabled=1, gateway_url="http://127.0.0.1:1", group_id="1203630000@g.us",
			notify_orders=1, notify_payments=1, only_sales_app=1, include_items=1, max_items=2,
			status="", linked_number="", last_error="", failed_checks=0,
		)

	def tearDown(self):
		frappe.local.request = self._request
		frappe.db.after_commit.reset()
		frappe.clear_document_cache(SETTINGS, SETTINGS)

	# ------------------------------------------------------------ settings

	def test_enabled_settings_need_gateway_and_group(self):
		doc = frappe.get_doc(SETTINGS)
		doc.enabled = 1
		doc.group_id = ""
		self.assertRaises(frappe.ValidationError, doc.validate)
		doc.group_id = "not a jid"
		self.assertRaises(frappe.ValidationError, doc.validate)
		doc.group_id = "1203630000@g.us"
		doc.gateway_url = "127.0.0.1:3010"
		self.assertRaises(frappe.ValidationError, doc.validate)
		doc.gateway_url = "http://127.0.0.1:3010/"
		doc.validate()
		self.assertEqual(doc.gateway_url, "http://127.0.0.1:3010")

	# ------------------------------------------------------------ messages

	def _order(self, docstatus=0):
		so = frappe.new_doc("Sales Order")
		so.name = "SO-TEST-1"
		so.customer = "CUST-1"
		so.customer_name = "Blue Traders"
		so.currency = "AED"
		so.docstatus = docstatus
		so.total_qty = 13
		so.grand_total = 1234.5
		so.modified = "2026-10-13 14:32:00"
		so.owner = "Administrator"
		for name, qty, uom in (("Water 500ml", 10, "Ctn"), ("Juice 1L", 2.5, "Nos"), ("Milk", 0.5, "Ltr")):
			so.append("items", {"item_code": name, "item_name": name, "qty": qty, "uom": uom})
		return so

	def test_order_message_lists_items_up_to_the_limit(self):
		text = build_message(self._order(), "created", "Administrator")
		self.assertIn("*🆕 New order* · SO-TEST-1", text)
		self.assertIn("Customer: Blue Traders", text)
		self.assertIn("Items (3):", text)
		self.assertIn("• Water 500ml × 10 Ctn", text)
		self.assertIn("• Juice 1L × 2.5 Nos", text)
		self.assertNotIn("Milk", text)
		self.assertIn("… and 1 more", text)
		self.assertIn("Total: AED 1,234.50", text)
		self.assertIn("Status: Draft", text)
		self.assertIn("13 Oct 2026, 14:32", text)

	def test_confirmed_and_cancelled_orders_change_the_heading(self):
		self.assertIn("*✅ Order confirmed*", build_message(self._order(1), "confirmed"))
		cancelled = build_message(self._order(2), "cancelled")
		self.assertIn("*❌ Order cancelled*", cancelled)
		self.assertIn("Status: Cancelled", cancelled)
		self.assertNotIn("Draft", cancelled)

	def test_order_message_without_items_shows_counts_only(self):
		_set_settings(include_items=0)
		text = build_message(self._order(), "created")
		self.assertIn("Items: 3 · 13 units", text)
		self.assertNotIn("•", text)

	def test_payment_message(self):
		pe = frappe.new_doc("Payment Entry")
		pe.name = "PE-TEST-1"
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		pe.party = "CUST-1"
		pe.party_name = "Blue Traders"
		pe.mode_of_payment = "Cash"
		pe.paid_amount = 500
		pe.paid_from_account_currency = "AED"
		pe.unallocated_amount = 100
		pe.modified = "2026-10-13 14:40:00"
		pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": "SI-1", "allocated_amount": 400})
		pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": "SI-2", "allocated_amount": 0})
		text = build_message(pe, "received", "Administrator")
		self.assertIn("*💰 Payment received* · PE-TEST-1", text)
		self.assertIn("Amount: AED 500.00 · Cash", text)
		self.assertIn("Against: SI-1 (AED 400.00)", text)
		self.assertNotIn("SI-2", text)
		self.assertIn("Unallocated (advance): AED 100.00", text)
		self.assertIn("Staff: Administrator", text)

	def test_unknown_doctype_has_no_message(self):
		self.assertIsNone(build_message(frappe.new_doc("ToDo"), "created"))

	# ------------------------------------------------------------- queuing

	def _fire(self, doc, *methods):
		"""Run the doc events, then the commit callbacks, capturing what was dispatched."""
		sent = []
		with patch.object(whatsapp, "_dispatch", side_effect=sent.append), \
				patch.object(whatsapp, "_load_doc", return_value=doc), \
				patch.object(whatsapp, "build_message", side_effect=lambda d, event, user=None: f"{d.name}:{event}:{user}"):
			for method in methods:
				on_document_event(doc, method)
			frappe.db.after_commit.run()
		return sent

	def test_save_then_submit_posts_once_as_confirmed(self):
		frappe.local.request = frappe._dict(path=APP_PATH)
		sent = self._fire(self._order(), "on_update", "on_submit")
		self.assertEqual(sent, [f"SO-TEST-1:confirmed:{frappe.session.user}"])

	def test_insert_posts_created_only_once(self):
		frappe.local.request = frappe._dict(path=APP_PATH)
		so = self._order()
		so.flags.in_insert = True
		sent = self._fire(so, "after_insert", "on_update")
		self.assertEqual(len(sent), 1)
		self.assertIn(":created:", sent[0])

	def test_desk_changes_are_ignored_unless_allowed(self):
		frappe.local.request = frappe._dict(path="/api/method/frappe.desk.form.save.savedocs")
		self.assertEqual(self._fire(self._order(), "on_submit"), [])
		_set_settings(only_sales_app=0)
		self.assertEqual(len(self._fire(self._order(), "on_submit")), 1)

	def test_disabled_settings_and_toggles_stop_posting(self):
		frappe.local.request = frappe._dict(path=APP_PATH)
		_set_settings(notify_orders=0)
		self.assertEqual(self._fire(self._order(), "on_submit"), [])
		_set_settings(notify_orders=1, enabled=0)
		self.assertEqual(self._fire(self._order(), "on_submit"), [])

	def test_only_customer_receipts_are_posted(self):
		frappe.local.request = frappe._dict(path=APP_PATH)
		pe = frappe.new_doc("Payment Entry")
		pe.name = "PE-TEST-2"
		pe.payment_type = "Pay"
		pe.party_type = "Supplier"
		self.assertEqual(self._fire(pe, "on_submit"), [])
		pe.payment_type = "Receive"
		pe.party_type = "Customer"
		self.assertEqual(len(self._fire(pe, "on_submit")), 1)

	def test_builder_failure_is_logged_not_raised(self):
		frappe.local.request = frappe._dict(path=APP_PATH)
		so = self._order()
		with patch.object(whatsapp, "_load_doc", side_effect=RuntimeError("boom")), \
				patch.object(whatsapp, "_dispatch") as dispatch, \
				patch.object(frappe, "log_error") as log_error:
			on_document_event(so, "on_submit")
			frappe.db.after_commit.run()
		dispatch.assert_not_called()
		log_error.assert_called_once()

	def test_send_group_message_needs_a_target(self):
		_set_settings(group_id="")
		self.assertRaises(whatsapp.GatewayError, whatsapp.send_group_message, "hi")

	def test_gateway_unreachable_is_a_gateway_error(self):
		self.assertRaises(whatsapp.GatewayError, whatsapp.send_group_message, "hi")

	# -------------------------------------------------------------- health

	def _settings(self):
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		return frappe.get_doc(SETTINGS)

	def test_health_records_the_link_and_only_alerts_on_a_change_for_the_worse(self):
		with patch.object(frappe, "log_error") as log_error:
			self.assertEqual(apply_health(self._settings(), "qr"), "Not linked")
			log_error.assert_not_called()  # linking for the first time is expected
			self.assertEqual(apply_health(self._settings(), "connected", number="97312345678"), "Connected")
			self.assertEqual(self._settings().linked_number, "97312345678")
			self.assertIsNone(apply_health(self._settings(), "connected", number="97312345678"))
			log_error.assert_not_called()
			# One failed check keeps the last good status; the second is Down, alerted once.
			self.assertIsNone(apply_health(self._settings(), "connecting"))
			self.assertEqual(self._settings().status, "Connected")
			self.assertEqual(apply_health(self._settings(), None, "connection refused"), "Down")
			self.assertEqual(self._settings().last_error, "connection refused")
			self.assertEqual(log_error.call_count, 1)
			self.assertIsNone(apply_health(self._settings(), None, "connection refused"))
			self.assertEqual(log_error.call_count, 1)
			# Back up: no alert, the error clears, the number stays.
			self.assertEqual(apply_health(self._settings(), "connected", number="97312345678"), "Connected")
			self.assertEqual(self._settings().last_error, "")
			self.assertEqual(log_error.call_count, 1)
			# Unlinked after being connected: alerted.
			self.assertEqual(apply_health(self._settings(), "logged_out", "closed (401)"), "Not linked")
			self.assertEqual(log_error.call_count, 2)
			self.assertEqual(self._settings().linked_number, "97312345678")

	def test_health_check_skips_without_a_gateway_and_treats_an_unreachable_one_as_failed(self):
		with patch.object(whatsapp, "gateway_request") as request:
			_set_settings(gateway_url="")
			check_gateway_health()
			request.assert_not_called()
			_set_settings(gateway_url="http://127.0.0.1:1")
			request.side_effect = whatsapp.GatewayError("Could not reach the WhatsApp gateway")
			check_gateway_health()
			self.assertEqual(self._settings().failed_checks, 1)
			self.assertEqual(self._settings().status, "Connecting")
			request.side_effect = None
			request.return_value = {"state": "connected", "number": "97312345678", "last_error": None}
			check_gateway_health()
			self.assertEqual(self._settings().status, "Connected")
			self.assertEqual(self._settings().failed_checks, 0)
