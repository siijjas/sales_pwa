"""Tests for the overall shift: Van and Field Sales profiles linked to a Counter Sales
profile hand their cash and activity over to the counter's shift (shift._linked_activity).

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_overall_shift
"""

import frappe

from sales_pwa.sales_app.finance import create_payment_entry
from sales_pwa.sales_app.sales import create_sales_order, submit_sales_order
from sales_pwa.sales_app.shift import close_shift, get_shift_closing_summary, open_shift, reopen_shift
from sales_pwa.sales_app.shift_report import get_closing_report, get_shift_summary
from sales_pwa.sales_app.tests import test_counter
from sales_pwa.sales_app.tests import test_shift_and_access as base
from sales_pwa.sales_app.utils import _driver_cache_key

VAN_USER = "_test_sales_app_linked_van@example.com"
REP_USER = "_test_sales_app_linked_rep@example.com"
VAN_PROFILE = f"{base.TEST_PREFIX} Linked Van"
REP_PROFILE = f"{base.TEST_PREFIX} Linked Rep"


class TestOverallShift(base.TestShiftAndAccessRegressions):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or frappe.db.get_value(
			"Price List", {"selling": 1, "enabled": 1}, "name"
		)
		for user, first in ((VAN_USER, "Linked Van"), (REP_USER, "Linked Rep")):
			if not frappe.db.exists("User", user):
				frappe.get_doc(
					{"doctype": "User", "email": user, "first_name": first, "user_type": "System User", "send_welcome_email": 0, "enabled": 1}
				).insert(ignore_permissions=True)
		for name in (VAN_PROFILE, REP_PROFILE):
			if frappe.db.exists("Sales Profile", name):
				frappe.delete_doc("Sales Profile", name, ignore_permissions=True, force=True)
		common = {
			"doctype": "Sales Profile",
			"company": cls.company,
			"is_active": 1,
			"default_cash_mode": cls.cash_mode,
			"cash_account": cls.cash_account,
			"allowed_payment_modes": [{"mode_of_payment": cls.cash_mode}],
			"allowed_customer_groups": [{"customer_group": cls.group_allowed}],
		}
		frappe.get_doc(
			{**common, "profile_name": VAN_PROFILE, "profile_type": "Van Sales", "separate_van_warehouse": 0, "source_warehouse": cls.source_warehouse,
			 "use_shifts": 1, "assigned_drivers": [{"driver_user": VAN_USER}]}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{**common, "profile_name": REP_PROFILE, "profile_type": "Field Sales", "use_shifts": 0, "assigned_drivers": [{"driver_user": REP_USER}]}
		).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		self._drop_open_shifts()
		self.addCleanup(self._drop_open_shifts)
		self.addCleanup(self._restore_van_profile)
		for user in (self.driver_user, VAN_USER, REP_USER):
			self.addCleanup(frappe.cache.delete_value, _driver_cache_key(user))

	def _drop_open_shifts(self):
		"""Each test starts with nobody on shift (the whole run is rolled back anyway)."""
		frappe.db.set_value(
			"Sales Shift Opening",
			{"driver": ["in", [self.driver_user, VAN_USER, REP_USER]], "status": "Open"},
			"status",
			"Closed",
		)

	_profile = test_counter.TestCounter._profile
	_make_counter = test_counter.TestCounter._make_counter
	_lines = test_counter.TestCounter._lines

	def _restore_van_profile(self):
		test_counter.TestCounter._restore_van_profile(self)

	def _counter(self, links=(VAN_PROFILE, REP_PROFILE), **values):
		return self._make_counter(use_shifts=1, linked_profiles=[{"linked_profile": p} for p in links], **values)

	def _as(self, user):
		frappe.cache.delete_value(_driver_cache_key(user))
		frappe.set_user(user)

	def _drawer(self, summary):
		return next(r for r in summary["payment_reconciliation"] if r["mode_of_payment"] == self.cash_mode)

	def _van_shift(self, float_amount, counted):
		"""The linked van opens with a float and closes having counted `counted` in cash."""
		self._as(VAN_USER)
		opening = open_shift(balance_details=frappe.as_json([{"mode_of_payment": self.cash_mode, "opening_amount": float_amount}]))
		closed = close_shift(opening["name"], reconciliation=frappe.as_json([{"mode_of_payment": self.cash_mode, "closing_amount": counted}]))
		self._as(self.driver_user)
		return closed["name"]

	# ─── the link ──────────────────────────────────────────────────────────

	def test_links_are_validated_and_keep_their_date(self):
		doc = self._counter(links=(VAN_PROFILE,))
		doc.reload()
		first = doc.linked_profiles[0].linked_on
		self.assertTrue(first)
		frappe.set_user("Administrator")
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.linked_profiles[0].linked_on, first)

		doc.append("linked_profiles", {"linked_profile": doc.name})
		with self.assertRaisesRegex(frappe.ValidationError, "itself"):
			doc.save(ignore_permissions=True)
		doc.reload()

		other = frappe.get_doc(
			{"doctype": "Sales Profile", "profile_name": f"{base.TEST_PREFIX} Other Counter", "profile_type": "Counter Sales", "company": self.company,
			 "is_active": 1, "source_warehouse": self.source_warehouse, "linked_profiles": [{"linked_profile": VAN_PROFILE}]}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "already hands over"):
			other.insert(ignore_permissions=True)

		van = frappe.get_doc("Sales Profile", VAN_PROFILE)
		van.append("linked_profiles", {"linked_profile": REP_PROFILE})
		van.save(ignore_permissions=True)
		self.assertEqual(van.linked_profiles, [])

	# ─── handover from staff on shifts ─────────────────────────────────────

	def test_van_closing_is_handed_over_to_the_counter_drawer(self):
		before_link = None
		self._counter(links=())
		before_link = self._van_shift(10, 10)  # closed before the link: never handed over
		self._counter(links=(VAN_PROFILE,))
		counter = open_shift(balance_details=frappe.as_json([{"mode_of_payment": self.cash_mode, "opening_amount": 100}]))

		self._as(VAN_USER)
		van_opening = open_shift(balance_details=frappe.as_json([{"mode_of_payment": self.cash_mode, "opening_amount": 30}]))
		self._as(self.driver_user)
		summary = get_shift_closing_summary()
		self.assertEqual([s["opening_shift"] for s in summary["linked"]["open_shifts"]], [van_opening["name"]])
		self.assertAlmostEqual(self._drawer(summary)["expected_amount"], 100, places=2)

		self._as(VAN_USER)
		van_closing = close_shift(van_opening["name"], reconciliation=frappe.as_json([{"mode_of_payment": self.cash_mode, "closing_amount": 28}]))["name"]
		self._as(self.driver_user)
		self.assertEqual(get_shift_closing_summary(opening_shift=None)["handover_to"], None)

		summary = get_shift_closing_summary()
		self.assertAlmostEqual(self._drawer(summary)["expected_amount"], 128, places=2)
		self.assertAlmostEqual(summary["total_handover"], 28, places=2)
		self.assertEqual([h["closing"] for h in summary["linked"]["handovers"]], [van_closing])
		self.assertEqual(summary["linked"]["open_shifts"], [])
		live = get_shift_summary()
		self.assertEqual([h["closing"] for h in live["linked"]["handovers"]], [van_closing])
		self.assertAlmostEqual(live["linked"]["drawer_amount"], 28, places=2)

		closed = close_shift(counter["name"], reconciliation=frappe.as_json([{"mode_of_payment": self.cash_mode, "closing_amount": 128}]))
		doc = frappe.get_doc("Sales Shift Closing", closed["name"])
		self.assertAlmostEqual(doc.total_handover, 28, places=2)
		self.assertAlmostEqual(doc.net_difference, 0, places=2)
		refs = {(t.reference_doctype, t.reference_name): t.linked_profile for t in doc.transactions}
		self.assertEqual(refs[("Sales Shift Closing", van_closing)], VAN_PROFILE)
		self.assertNotIn(("Sales Shift Closing", before_link), refs)

		report = get_closing_report(closed["name"])
		self.assertEqual([h["closing"] for h in report["linked"]["handovers"]], [van_closing])
		self.assertAlmostEqual(report["linked"]["total_handover"], 28, places=2)
		self.assertEqual(report["documents"]["payments"], [])

		# Its cash now sits in a closed counter shift: the van's closing can't be reopened under it.
		frappe.set_user("Administrator")
		with self.assertRaisesRegex(frappe.ValidationError, "handed over"):
			reopen_shift(van_closing)

	def test_linked_van_sees_which_counter_it_hands_over_to(self):
		self._counter(links=(VAN_PROFILE,))
		self._as(VAN_USER)
		open_shift(balance_details="[]")
		counter = frappe.db.get_value("Sales Profile", {"profile_name": f"{base.TEST_PREFIX} Profile"}, "name")
		self.assertEqual(get_shift_closing_summary()["handover_to"], counter)

	# ─── staff without shifts ──────────────────────────────────────────────

	def test_field_rep_without_shifts_rolls_in_directly(self):
		self._counter(links=(REP_PROFILE,))
		counter = open_shift(balance_details="[]")
		self._as(REP_USER)
		so = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 1, "rate": 40}])["name"]
		submit_sales_order(so)
		pe = create_payment_entry(self.customer_allowed, self.cash_mode, 15, "[]", sales_order=so)
		self._as(self.driver_user)

		summary = get_shift_closing_summary()
		self.assertAlmostEqual(self._drawer(summary)["expected_amount"], 15, places=2)
		self.assertAlmostEqual(summary["total_linked_collections"], 15, places=2)
		self.assertAlmostEqual(summary["total_linked_sales"], frappe.db.get_value("Sales Order", so, "grand_total"), places=2)
		self.assertAlmostEqual(summary["total_collections"], 0, places=2)
		self.assertAlmostEqual(summary["total_sales"], 0, places=2)

		closed = close_shift(counter["name"], reconciliation=frappe.as_json([{"mode_of_payment": self.cash_mode, "closing_amount": 15}]))
		doc = frappe.get_doc("Sales Shift Closing", closed["name"])
		refs = {(t.reference_doctype, t.reference_name): t.linked_profile for t in doc.transactions}
		self.assertEqual(refs[("Sales Order", so)], REP_PROFILE)
		self.assertEqual(refs[("Payment Entry", pe)], REP_PROFILE)

		report = get_closing_report(closed["name"])
		rep = report["linked"]["direct"][0]
		self.assertEqual((rep["driver"], rep["orders_count"], rep["payments_count"]), (REP_USER, 1, 1))
		self.assertAlmostEqual(rep["collections_total"], 15, places=2)
		self.assertEqual(report["totals"]["sales_orders_count"], 0)
		self.assertEqual(report["collections"], [])

		# Claimed once: the counter's next shift does not count them again.
		again = open_shift(balance_details="[]")
		self.assertAlmostEqual(get_shift_closing_summary(again["name"])["total_linked_collections"], 0, places=2)

	def test_unlinked_counter_is_unchanged(self):
		self._counter(links=())
		open_shift(balance_details="[]")
		summary = get_shift_closing_summary()
		self.assertEqual(summary["linked"], {"handovers": [], "open_shifts": []})
		self.assertEqual(summary["total_handover"], 0)

	# ─── parent tests, not repeated here ───────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
