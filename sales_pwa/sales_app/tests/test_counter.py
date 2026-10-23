"""Tests for the Counter: the Counter Sales profile type and the fast order entry
endpoints in sales_pwa.sales_app.counter.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_counter
"""

import frappe

from sales_pwa.sales_app.counter import (
	create_counter_sale,
	get_counter_queue,
	preview_counter_totals,
	search_counter_items,
)
from sales_pwa.sales_app.driver import get_app_context
from sales_pwa.sales_app.sales import create_sales_order
from sales_pwa.sales_app.tests import test_shift_and_access as base
from sales_pwa.sales_app.utils import _capabilities, _driver_cache_key

BARCODE = "_TESTSALESAPPBC001"


class TestCounter(base.TestShiftAndAccessRegressions):
	"""Reuses the shift tests' driver / Sales Profile / customer / item fixtures; the
	parent's own tests are blanked out below so they don't run twice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or frappe.db.get_value(
			"Price List", {"selling": 1, "enabled": 1}, "name"
		)
		if not cls.price_list:
			raise base.unittest.SkipTest("No selling price list on this site")
		cls.item_rate = 42.0
		if not frappe.db.exists("Item Price", {"item_code": cls.item_code, "price_list": cls.price_list}):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": cls.item_code,
					"price_list": cls.price_list,
					"price_list_rate": cls.item_rate,
					"selling": 1,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"Item Price", {"item_code": cls.item_code, "price_list": cls.price_list}, "price_list_rate", cls.item_rate
			)
		item = frappe.get_doc("Item", cls.item_code)
		if not any(row.barcode == BARCODE for row in item.barcodes):
			item.append("barcodes", {"barcode": BARCODE})
			item.save(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		self.addCleanup(self._restore_van_profile)
		self.addCleanup(frappe.cache.delete_value, _driver_cache_key(self.driver_user))

	# ─── helpers ───────────────────────────────────────────────────────────

	def _profile(self):
		frappe.set_user("Administrator")
		return frappe.get_doc("Sales Profile", self.van_profile)

	def _make_counter(self, **values):
		doc = self._profile()
		doc.profile_type = "Counter Sales"
		doc.source_warehouse = self.source_warehouse
		doc.default_customer = self.customer_allowed
		doc.selling_price_list = self.price_list
		doc.allow_rate_change = 1
		doc.allow_discount_change = 1
		doc.use_shifts = 0
		for field, value in values.items():
			doc.set(field, value)
		doc.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		frappe.set_user(self.driver_user)
		return doc

	def _make_field_sales(self):
		doc = self._profile()
		doc.profile_type = "Field Sales"
		doc.use_shifts = 0
		doc.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		frappe.set_user(self.driver_user)

	def _restore_van_profile(self):
		doc = self._profile()
		doc.profile_type = "Van Sales"
		doc.separate_van_warehouse = 1
		doc.source_warehouse = self.source_warehouse
		doc.van_warehouse = self.van_warehouse
		doc.stock_warehouse = None
		doc.default_customer = None
		doc.selling_price_list = None
		doc.allow_rate_change = 0
		doc.allow_discount_change = 0
		doc.allow_credit_sale = 1
		doc.use_shifts = 1
		doc.require_open_shift = 0
		doc.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))

	def _lines(self, qty=2, rate=None):
		line = {"item_code": self.item_code, "qty": qty}
		if rate is not None:
			line["rate"] = rate
		return [line]

	# ─── profile type ──────────────────────────────────────────────────────

	def test_counter_profile_sells_from_main_warehouse_without_a_van(self):
		doc = self._make_counter()
		doc.reload()
		self.assertEqual(doc.profile_type, "Counter Sales")
		self.assertEqual(doc.source_warehouse, self.source_warehouse)
		self.assertIsNone(doc.van_warehouse)
		self.assertFalse(doc.separate_van_warehouse)
		self.assertEqual(doc.default_customer, self.customer_allowed)
		self.assertEqual(doc.selling_warehouse, self.source_warehouse)

	def test_counter_profile_needs_a_main_warehouse(self):
		doc = self._profile()
		doc.profile_type = "Counter Sales"
		doc.source_warehouse = None
		with self.assertRaisesRegex(frappe.ValidationError, "needs a Main Warehouse"):
			doc.save(ignore_permissions=True)

	def test_default_customer_must_exist_and_is_counter_only(self):
		doc = self._profile()
		doc.profile_type = "Counter Sales"
		doc.default_customer = "_No Such Customer"
		with self.assertRaisesRegex(frappe.ValidationError, "does not exist|Could not find"):
			doc.save(ignore_permissions=True)

		doc = self._make_counter()
		doc.profile_type = "Van Sales"
		doc.van_warehouse = self.van_warehouse
		doc.separate_van_warehouse = 1
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertIsNone(doc.default_customer)

	def test_capabilities_for_counter(self):
		counter = _capabilities({"profile_type": "Counter Sales", "use_shifts": 1, "source_warehouse": "X"})
		self.assertTrue(counter["is_counter_sales"])
		self.assertTrue(counter["can_counter_sell"])
		self.assertTrue(counter["can_invoice"] and counter["can_deliver"] and counter["can_view_stock"])
		self.assertFalse(counter["can_load_stock"])
		self.assertFalse(counter["has_van_warehouse"])
		self.assertFalse(counter["is_field_sales"])

		for profile_type in ("Van Sales", "Field Sales"):
			caps = _capabilities({"profile_type": profile_type})
			self.assertFalse(caps["is_counter_sales"], profile_type)
			self.assertFalse(caps["can_counter_sell"], profile_type)

		# Managers see every screen, the Counter included.
		self.assertTrue(_capabilities(None)["can_counter_sell"])

	def test_app_context_carries_default_customer(self):
		self._make_counter()
		ctx = get_app_context()
		config = ctx["driver_config"]
		self.assertEqual(config["profile_type"], "Counter Sales")
		self.assertEqual(config["default_customer"], self.customer_allowed)
		self.assertEqual(config["default_customer_name"], frappe.db.get_value("Customer", self.customer_allowed, "customer_name"))
		self.assertEqual(config["selling_warehouse"], self.source_warehouse)
		self.assertTrue(ctx["capabilities"]["can_counter_sell"])

	# ─── access ────────────────────────────────────────────────────────────

	def test_other_profile_types_cannot_use_the_counter(self):
		self._make_field_sales()
		with self.assertRaises(frappe.PermissionError):
			search_counter_items("x")
		with self.assertRaises(frappe.PermissionError):
			get_counter_queue()
		with self.assertRaises(frappe.PermissionError):
			create_counter_sale(self.customer_allowed, self._lines())

	def test_manager_without_profile_can_use_the_counter(self):
		frappe.set_user("Administrator")
		result = search_counter_items(self.item_code)
		self.assertTrue(any(row["item_code"] == self.item_code for row in result["items"]))
		self.assertIn("held", get_counter_queue())

	# ─── search ────────────────────────────────────────────────────────────

	def test_search_exact_code_ranks_first_with_price(self):
		self._make_counter()
		result = search_counter_items(self.item_code)
		self.assertEqual(result["price_list"], self.price_list)
		self.assertEqual(result["warehouse"], self.source_warehouse)
		first = result["items"][0]
		self.assertEqual(first["item_code"], self.item_code)
		self.assertTrue(first["exact"])
		self.assertAlmostEqual(first["price_list_rate"], self.item_rate, places=2)
		self.assertEqual(first["stock_uom"], self.uom)
		self.assertIn("must_be_whole_number", first)

	def test_search_matches_barcode_and_name_fragment(self):
		self._make_counter()
		by_barcode = search_counter_items(BARCODE)["items"]
		self.assertEqual(by_barcode[0]["item_code"], self.item_code)
		self.assertTrue(by_barcode[0]["exact"])

		fragment = self.item_code.split()[-1].lower()
		by_name = search_counter_items(fragment)["items"]
		self.assertTrue(any(row["item_code"] == self.item_code for row in by_name))
		self.assertFalse(any(row["exact"] for row in by_name if row["item_code"] != self.item_code))

		self.assertEqual(search_counter_items("zzz-no-such-item-zzz")["items"], [])

	# ─── preview ───────────────────────────────────────────────────────────

	def test_preview_totals_match_what_the_order_would_carry(self):
		self._make_counter()
		preview = preview_counter_totals(self.customer_allowed, self._lines(qty=3))
		self.assertIsNone(preview["error"])
		self.assertEqual(len(preview["lines"]), 1)
		self.assertAlmostEqual(preview["lines"][0]["rate"], self.item_rate, places=2)
		self.assertAlmostEqual(preview["total"], 3 * self.item_rate, places=2)
		self.assertAlmostEqual(preview["total_qty"], 3, places=2)
		self.assertGreaterEqual(preview["grand_total"], preview["net_total"])
		self.assertEqual(preview["short_items"], [])
		self.assertEqual(preview["warehouse"], self.source_warehouse)

		discounted = preview_counter_totals(self.customer_allowed, self._lines(qty=3), discount_percent=10)
		self.assertIsNone(discounted["error"])
		self.assertAlmostEqual(discounted["discount_amount"], preview["grand_total"] * 0.10, places=2)
		self.assertAlmostEqual(discounted["grand_total"], preview["grand_total"] * 0.90, places=2)

	def test_preview_reports_profile_refusals_instead_of_failing(self):
		self._make_counter(allow_rate_change=0)
		preview = preview_counter_totals(self.customer_allowed, self._lines(qty=1, rate=self.item_rate + 5))
		self.assertTrue(preview["error"])
		self.assertEqual(preview["grand_total"], 0)
		self.assertEqual(preview["lines"], [])

	# ─── the sale ──────────────────────────────────────────────────────────

	def test_create_counter_sale_submits_an_order(self):
		self._make_counter()
		result = create_counter_sale(self.customer_allowed, self._lines(qty=2))
		self.assertIsNone(result["invoice"])
		so = frappe.get_doc("Sales Order", result["order"])
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(so.customer, self.customer_allowed)
		self.assertEqual(so.set_warehouse, self.source_warehouse)
		self.assertEqual(so.owner, self.driver_user)
		self.assertAlmostEqual(so.total, 2 * self.item_rate, places=2)
		self.assertAlmostEqual(result["grand_total"], so.grand_total, places=2)

	def test_create_counter_sale_keeps_two_lines_of_the_same_item(self):
		self._make_counter()
		lines = [{"item_code": self.item_code, "qty": 1}, {"item_code": self.item_code, "qty": 2}]
		so = frappe.get_doc("Sales Order", create_counter_sale(self.customer_allowed, lines)["order"])
		self.assertEqual([row.qty for row in so.items], [1, 2])

	def test_create_counter_sale_invoices_and_collects_in_one_request(self):
		self._make_counter()
		result = create_counter_sale(
			self.customer_allowed, self._lines(qty=2), invoice=1, mark_as_paid=1, mode_of_payment=self.cash_mode
		)
		self.assertTrue(result["invoice"])
		so = frappe.get_doc("Sales Order", result["order"])
		self.assertEqual(so.docstatus, 1)
		sinv = frappe.get_doc("Sales Invoice", result["invoice"])
		self.assertEqual(sinv.docstatus, 1)
		self.assertTrue(sinv.update_stock)
		self.assertEqual(sinv.items[0].sales_order, so.name)
		self.assertAlmostEqual(sinv.outstanding_amount, 0, places=2)
		self.assertAlmostEqual(result["outstanding_amount"], 0, places=2)
		self.assertAlmostEqual(result["grand_total"], sinv.grand_total, places=2)
		payment = frappe.get_all(
			"Payment Entry Reference", filters={"reference_name": sinv.name}, fields=["parent", "allocated_amount"]
		)
		self.assertEqual(len(payment), 1)
		self.assertAlmostEqual(payment[0].allocated_amount, sinv.grand_total if sinv.disable_rounded_total else sinv.rounded_total, places=2)

	def test_create_counter_sale_credit_invoice_stays_outstanding(self):
		self._make_counter()
		result = create_counter_sale(self.customer_allowed, self._lines(qty=1), invoice=1, mark_as_paid=0)
		sinv = frappe.get_doc("Sales Invoice", result["invoice"])
		self.assertGreater(sinv.outstanding_amount, 0)

	def test_create_counter_sale_resumes_a_held_order(self):
		self._make_counter()
		held = create_sales_order(self.customer_allowed, self._lines(qty=1))
		self.assertEqual(frappe.db.get_value("Sales Order", held["name"], "docstatus"), 0)
		result = create_counter_sale(self.customer_allowed, self._lines(qty=5), order_name=held["name"])
		self.assertEqual(result["order"], held["name"])
		so = frappe.get_doc("Sales Order", held["name"])
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(so.items[0].qty, 5)

	def test_create_counter_sale_changes_a_submitted_order_in_place(self):
		self._make_counter()
		pending = create_counter_sale(self.customer_allowed, self._lines(qty=1))["order"]
		queued = next(r for r in get_counter_queue()["to_invoice"] if r["name"] == pending)
		self.assertEqual((queued["per_billed"], queued["per_delivered"]), (0, 0))

		result = create_counter_sale(
			self.customer_allowed, self._lines(qty=4), order_name=pending, invoice=1, mark_as_paid=1, mode_of_payment=self.cash_mode
		)
		self.assertEqual(result["order"], pending)
		so = frappe.get_doc("Sales Order", pending)
		self.assertEqual((so.docstatus, so.items[0].qty, so.per_billed), (1, 4, 100))
		self.assertEqual(frappe.get_doc("Sales Invoice", result["invoice"]).items[0].qty, 4)

		# Another customer's cart cannot take over the submitted order.
		other = create_counter_sale(self.customer_allowed, self._lines(qty=1))["order"]
		with self.assertRaisesRegex(frappe.ValidationError, "another customer"):
			create_counter_sale(f"{self.customer_allowed} X", self._lines(qty=1), order_name=other)

	def test_refused_invoice_leaves_no_submitted_order_behind(self):
		self._make_counter(allow_credit_sale=0)
		before = frappe.db.count("Sales Order", {"owner": self.driver_user, "customer": self.customer_allowed})
		with self.assertRaises(frappe.PermissionError):
			create_counter_sale(self.customer_allowed, self._lines(qty=1), invoice=1, mark_as_paid=0)
		with self.assertRaisesRegex(frappe.ValidationError, "mode of payment"):
			create_counter_sale(self.customer_allowed, self._lines(qty=1), invoice=1, mark_as_paid=1)
		after = frappe.db.count("Sales Order", {"owner": self.driver_user, "customer": self.customer_allowed})
		self.assertEqual(before, after)

	def test_create_counter_sale_respects_customer_scope(self):
		self._make_counter()
		with self.assertRaises(frappe.PermissionError):
			create_counter_sale(self.customer_denied, self._lines(qty=1))

	# ─── queue ─────────────────────────────────────────────────────────────

	def test_queue_lists_held_pending_and_todays_invoices(self):
		self._make_counter()
		held = create_sales_order(self.customer_allowed, self._lines(qty=1))["name"]
		pending = create_counter_sale(self.customer_allowed, self._lines(qty=1))["order"]
		invoiced = create_counter_sale(
			self.customer_allowed, self._lines(qty=1), invoice=1, mark_as_paid=1, mode_of_payment=self.cash_mode
		)
		queue = get_counter_queue()
		self.assertIn(held, [row["name"] for row in queue["held"]])
		self.assertIn(pending, [row["name"] for row in queue["to_invoice"]])
		self.assertNotIn(invoiced["order"], [row["name"] for row in queue["to_invoice"]])
		self.assertIn(invoiced["invoice"], [row["name"] for row in queue["invoices_today"]])
		row = next(r for r in queue["invoices_today"] if r["name"] == invoiced["invoice"])
		self.assertEqual(row["customer"], self.customer_allowed)
		self.assertAlmostEqual(row["outstanding_amount"], 0, places=2)

	# ─── parent tests, not repeated here ───────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
