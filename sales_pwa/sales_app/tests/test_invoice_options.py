"""Sales Invoice Options: numbering series + tax template per option, enabled per
Sales Profile, previewed before the invoice is created.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_invoice_options
"""

import frappe
from frappe.utils import flt

from sales_pwa.sales_app.invoice_option import list_invoice_options, resolve_invoice_option, save_invoice_option
from sales_pwa.sales_app.sales import create_sales_invoice, create_sales_order, preview_sales_invoice, submit_sales_order
from sales_pwa.sales_app.tests import test_shift_and_access as base
from sales_pwa.sales_app.utils import _driver_cache_key

TEST_PREFIX = base.TEST_PREFIX


class TestInvoiceOptions(base.TestShiftAndAccessRegressions):
	"""Reuses the shift tests' driver / Sales Profile / customer / item fixtures; the
	parent's own tests are blanked out below so they don't run twice."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		series = frappe.get_meta("Sales Invoice").get_naming_series_options()
		self.series = [s for s in series if s]
		self.option = save_invoice_option(
			{"option_name": f"{TEST_PREFIX} Option A", "naming_series": self.series[0], "taxes_and_charges": None}
		)
		self.addCleanup(self._cleanup)
		frappe.set_user(self.driver_user)

	def _cleanup(self):
		frappe.set_user("Administrator")
		profile = frappe.get_doc("Sales Profile", self.van_profile)
		profile.set("invoice_options", [])
		profile.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		for name in frappe.get_all("Sales Invoice Option", filters={"option_name": ["like", f"{TEST_PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("Sales Invoice Option", name, ignore_permissions=True, force=True)

	def _enable_on_profile(self, *names, default=None):
		frappe.set_user("Administrator")
		profile = frappe.get_doc("Sales Profile", self.van_profile)
		profile.set("invoice_options", [])
		for name in names:
			profile.append("invoice_options", {"invoice_option": name, "is_default": 1 if name == default else 0})
		profile.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		frappe.set_user(self.driver_user)

	def _submitted_order(self):
		so = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 2, "rate": 10}])
		submit_sales_order(so["name"])
		return so["name"]

	# ─── master validation ─────────────────────────────────────────────────

	def test_option_needs_a_real_sales_invoice_series(self):
		frappe.set_user("Administrator")
		with self.assertRaisesRegex(frappe.ValidationError, "not a Sales Invoice naming series"):
			save_invoice_option({"option_name": f"{TEST_PREFIX} Bad", "naming_series": "NOPE-.#####"})

	def test_profile_defaults_first_option_when_none_marked(self):
		self._enable_on_profile(self.option["name"])
		frappe.set_user("Administrator")
		rows = frappe.get_doc("Sales Profile", self.van_profile).invoice_options
		self.assertTrue(rows[0].is_default)

	# ─── resolution ────────────────────────────────────────────────────────

	def test_staff_see_only_their_profile_options(self):
		self._enable_on_profile(self.option["name"], default=self.option["name"])
		names = [o["name"] for o in list_invoice_options()]
		self.assertEqual(names, [self.option["name"]])
		# A profile without options resolves to nothing: historical invoicing.
		self.assertIsNone(resolve_invoice_option({"invoice_options": []}, None))
		# Naming an option the profile does not list is refused.
		with self.assertRaises(frappe.PermissionError):
			resolve_invoice_option({"invoice_options": []}, self.option["name"])

	# ─── preview and create agree ──────────────────────────────────────────

	def test_preview_matches_created_invoice(self):
		self._enable_on_profile(self.option["name"], default=self.option["name"])
		so = self._submitted_order()
		preview = preview_sales_invoice(so, self.option["name"])
		self.assertEqual(preview["naming_series"], self.series[0])
		self.assertTrue(preview["proposed_name"])
		self.assertEqual(preview["net_total"], 20)
		self.assertEqual(preview["invoice_option"]["name"], self.option["name"])

		name = create_sales_invoice(so, invoice_option=self.option["name"])
		inv = frappe.get_doc("Sales Invoice", name)
		self.assertEqual(inv.naming_series, self.series[0])
		self.assertEqual(inv.grand_total, preview["grand_total"])
		self.assertFalse(inv.taxes)

	def test_default_option_applies_when_none_named(self):
		self._enable_on_profile(self.option["name"], default=self.option["name"])
		so = self._submitted_order()
		preview = preview_sales_invoice(so)
		self.assertEqual(preview["invoice_option"]["name"], self.option["name"])

	def test_option_retaxes_the_order_to_match_the_invoice(self):
		template = frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": self.company, "disabled": 0}, "name"
		)
		if not template:
			self.skipTest("No Sales Taxes and Charges Template on this company")
		frappe.set_user("Administrator")
		taxed = save_invoice_option(
			{"option_name": f"{TEST_PREFIX} Taxed", "naming_series": self.series[0], "taxes_and_charges": template}
		)
		self._enable_on_profile(taxed["name"], default=taxed["name"])
		so = self._submitted_order()
		before = frappe.db.get_value("Sales Order", so, "grand_total")

		preview = preview_sales_invoice(so, taxed["name"])
		self.assertTrue(preview["order_taxes_will_update"])
		self.assertEqual(preview["order_grand_total"], before)

		name = create_sales_invoice(so, invoice_option=taxed["name"])
		order = frappe.get_doc("Sales Order", so)
		inv = frappe.get_doc("Sales Invoice", name)
		self.assertEqual(order.taxes_and_charges, template)
		self.assertEqual(order.grand_total, inv.grand_total)
		self.assertEqual(order.docstatus, 1)
		self.assertEqual(sum(flt(r.payment_amount) for r in order.payment_schedule), order.rounded_total or order.grand_total)

	# ─── parent's tests are not re-run here ────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
