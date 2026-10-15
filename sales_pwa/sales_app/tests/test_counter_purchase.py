"""Tests for the Counter's Purchase screen (sales_pwa.sales_app.counter_purchase) and
for how its purchases and supplier payments land on the shift closing.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_counter_purchase
"""

import frappe

from sales_pwa.sales_app.cash_movement import create_cash_movement
from sales_pwa.sales_app.counter import create_counter_sale
from sales_pwa.sales_app.counter_purchase import (
	bill_counter_purchase,
	create_counter_purchase,
	get_counter_purchase,
	get_purchase_queue,
	preview_counter_purchase,
	search_purchase_items,
	search_suppliers,
)
from sales_pwa.sales_app.shift import close_shift, get_shift_closing_summary, open_shift
from sales_pwa.sales_app.shift_report import get_closing_report
from sales_pwa.sales_app.tests import test_counter
from sales_pwa.sales_app.tests import test_shift_and_access as base
from sales_pwa.sales_app.utils import _capabilities, _driver_cache_key

SUPPLIER = f"{base.TEST_PREFIX} Supplier"


class TestCounterPurchase(base.TestShiftAndAccessRegressions):
	"""Same fixtures as the Counter tests; the parent's own tests are blanked below."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or frappe.db.get_value(
			"Price List", {"selling": 1, "enabled": 1}, "name"
		)
		if not frappe.db.exists("Supplier", SUPPLIER):
			group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
			frappe.get_doc(
				{"doctype": "Supplier", "supplier_name": SUPPLIER, "supplier_group": group}
			).insert(ignore_permissions=True)
		cls.supplier = frappe.db.get_value("Supplier", {"supplier_name": SUPPLIER}, "name")

	def setUp(self):
		super().setUp()
		self.addCleanup(self._restore_van_profile)
		self.addCleanup(frappe.cache.delete_value, _driver_cache_key(self.driver_user))

	_profile = test_counter.TestCounter._profile
	def _make_counter(self, **values):
		values.setdefault("allow_counter_purchase", 1)
		return test_counter.TestCounter._make_counter(self, **values)

	_restore_van_profile = test_counter.TestCounter._restore_van_profile
	_lines = test_counter.TestCounter._lines

	def _cart(self, qty=3, rate=7.5):
		return [{"item_code": self.item_code, "qty": qty, "rate": rate}]

	# ─── access ────────────────────────────────────────────────────────────

	def test_capabilities(self):
		self.assertTrue(_capabilities(None)["can_counter_purchase"])
		self.assertTrue(_capabilities(None)["can_record_expense"])
		self.assertTrue(_capabilities({"profile_type": "Counter Sales"})["can_counter_purchase"])
		self.assertFalse(_capabilities({"profile_type": "Counter Sales", "allow_counter_purchase": 0})["can_counter_purchase"])
		self.assertFalse(_capabilities({"profile_type": "Van Sales"})["can_counter_purchase"])
		self.assertFalse(_capabilities({"profile_type": "Counter Sales", "use_shifts": 0})["can_record_expense"])

	def test_profile_switch_and_other_profile_types_are_refused(self):
		self._make_counter(allow_counter_purchase=0)
		with self.assertRaises(frappe.PermissionError):
			search_suppliers("")
		self._restore_van_profile()
		frappe.set_user(self.driver_user)
		with self.assertRaises(frappe.PermissionError):
			create_counter_purchase(self.supplier, self._cart())

	# ─── search ────────────────────────────────────────────────────────────

	def test_search_suppliers_and_items(self):
		self._make_counter()
		rows = search_suppliers(SUPPLIER[:12])
		self.assertIn(self.supplier, [r["name"] for r in rows])
		res = search_purchase_items(self.item_code, self.supplier)
		self.assertEqual(res["items"][0]["item_code"], self.item_code)
		self.assertTrue(res["items"][0]["exact"])
		self.assertEqual(res["warehouse"], self.source_warehouse)

	def test_search_prefers_the_suppliers_own_buying_price(self):
		self._make_counter()
		frappe.set_user("Administrator")
		price_list = frappe.db.get_single_value("Buying Settings", "buying_price_list") or frappe.db.get_value(
			"Price List", {"buying": 1, "enabled": 1}, "name"
		)
		if not price_list:
			self.skipTest("No buying price list on this site")
		for supplier, rate in ((None, 5), (self.supplier, 4)):
			key = {"item_code": self.item_code, "price_list": price_list, "supplier": supplier or ("is", "not set")}
			existing = frappe.db.get_value("Item Price", key, "name")
			if existing:
				frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
			else:
				frappe.get_doc({"doctype": "Item Price", "item_code": self.item_code, "price_list": price_list, "price_list_rate": rate, "buying": 1, "supplier": supplier}).insert(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(self.driver_user))
		frappe.set_user(self.driver_user)
		self.assertEqual(search_purchase_items(self.item_code, self.supplier)["items"][0]["price_list_rate"], 4)
		self.assertEqual(search_purchase_items(self.item_code, None)["items"][0]["price_list_rate"], 5)

	# ─── order ─────────────────────────────────────────────────────────────

	def test_preview_keeps_the_typed_rate(self):
		self._make_counter()
		preview = preview_counter_purchase(self.supplier, self._cart(qty=4, rate=2.5))
		self.assertIsNone(preview["error"])
		self.assertAlmostEqual(preview["total"], 10, places=2)
		self.assertEqual(preview["lines"][0]["rate"], 2.5)
		bad = preview_counter_purchase(self.supplier, [{"item_code": self.item_code, "qty": 0}])
		self.assertTrue(bad["error"])

	def test_hold_then_resume_then_submit(self):
		self._make_counter()
		held = create_counter_purchase(self.supplier, self._cart(qty=1), hold=1)
		self.assertEqual(held["docstatus"], 0)
		self.assertIn(held["order"], [r["name"] for r in get_purchase_queue()["held"]])
		self.assertEqual(get_counter_purchase(held["order"])["items"][0]["qty"], 1)
		done = create_counter_purchase(self.supplier, self._cart(qty=6, rate=3), order_name=held["order"])
		self.assertEqual(done["order"], held["order"])
		po = frappe.get_doc("Purchase Order", done["order"])
		self.assertEqual(po.docstatus, 1)
		self.assertEqual(po.items[0].qty, 6)
		self.assertEqual(po.items[0].rate, 3)
		self.assertEqual(po.set_warehouse, self.source_warehouse)
		self.assertEqual(po.owner, self.driver_user)
		self.assertIn(po.name, [r["name"] for r in get_purchase_queue()["to_bill"]])

	def test_bill_paid_from_the_drawer(self):
		self._make_counter()
		order = create_counter_purchase(self.supplier, self._cart(qty=2, rate=10))["order"]
		result = bill_counter_purchase(order, mark_as_paid=1, mode_of_payment=self.cash_mode, bill_no="SUP-77")
		pi = frappe.get_doc("Purchase Invoice", result["invoice"])
		self.assertEqual(pi.docstatus, 1)
		self.assertTrue(pi.update_stock)
		self.assertEqual(pi.bill_no, "SUP-77")
		self.assertEqual(pi.items[0].purchase_order, order)
		self.assertAlmostEqual(pi.outstanding_amount, 0, places=2)
		pe = frappe.get_doc("Payment Entry", result["payment"])
		self.assertEqual((pe.payment_type, pe.party, pe.mode_of_payment), ("Pay", self.supplier, self.cash_mode))
		queue = get_purchase_queue()
		self.assertNotIn(order, [r["name"] for r in queue["to_bill"]])
		self.assertIn(pi.name, [r["name"] for r in queue["bills_today"]])
		with self.assertRaisesRegex(frappe.ValidationError, "already billed"):
			bill_counter_purchase(order, bill_no="SUP-77B")

	def test_bill_on_credit_and_refusals(self):
		self._make_counter()
		held = create_counter_purchase(self.supplier, self._cart(qty=1), hold=1)["order"]
		with self.assertRaisesRegex(frappe.ValidationError, "Submit"):
			bill_counter_purchase(held, bill_no="A")
		order = create_counter_purchase(self.supplier, self._cart(qty=1, rate=8))["order"]
		with self.assertRaisesRegex(frappe.ValidationError, "mode of payment"):
			bill_counter_purchase(order, mark_as_paid=1, bill_no="A")
		with self.assertRaises(frappe.ValidationError):
			bill_counter_purchase(order, mark_as_paid=1, mode_of_payment="Wire Transfer", bill_no="A")
		if frappe.get_meta("Purchase Invoice").get_field("bill_no").reqd:
			with self.assertRaisesRegex(frappe.ValidationError, "invoice number"):
				bill_counter_purchase(order)
		result = bill_counter_purchase(order, bill_no="SUP-78")
		self.assertIsNone(result["payment"])
		self.assertAlmostEqual(result["outstanding_amount"], 8, places=2)

	def test_others_purchase_orders_are_out_of_reach(self):
		self._make_counter()
		frappe.set_user("Administrator")
		other = create_counter_purchase(self.supplier, self._cart(qty=1))["order"]
		frappe.set_user(self.driver_user)
		with self.assertRaises(frappe.PermissionError):
			bill_counter_purchase(other, bill_no="X")
		with self.assertRaises(frappe.PermissionError):
			get_counter_purchase(other)

	# ─── shift ─────────────────────────────────────────────────────────────

	def test_shift_closing_reconciles_sales_expenses_and_supplier_payments(self):
		self._make_counter(use_shifts=1, allow_expense=1, cash_movement_max_amount=0)
		opening = open_shift(balance_details=frappe.as_json([{"mode_of_payment": self.cash_mode, "opening_amount": 100}]))
		sale = create_counter_sale(self.customer_allowed, self._lines(qty=1, rate=50), invoice=1, mark_as_paid=1, mode_of_payment=self.cash_mode)
		paid_in = sale["rounded_total"] or sale["grand_total"]
		create_cash_movement("Expense", 5, expense_account=self.expense_account, remarks="Tea")
		order = create_counter_purchase(self.supplier, self._cart(qty=2, rate=10))["order"]
		bill = bill_counter_purchase(order, mark_as_paid=1, mode_of_payment=self.cash_mode, bill_no="SUP-79")
		credit = create_counter_purchase(self.supplier, self._cart(qty=1, rate=4))["order"]

		summary = get_shift_closing_summary()
		drawer = next(r for r in summary["payment_reconciliation"] if r["mode_of_payment"] == self.cash_mode)
		self.assertAlmostEqual(drawer["expected_amount"], 100 + paid_in - 5 - 20, places=2)
		self.assertAlmostEqual(summary["total_supplier_payments"], 20, places=2)
		self.assertAlmostEqual(summary["total_purchases"], 24, places=2)
		self.assertAlmostEqual(summary["total_collections"], paid_in, places=2)

		closed = close_shift(opening["name"], reconciliation=frappe.as_json([{"mode_of_payment": self.cash_mode, "closing_amount": drawer["expected_amount"]}]))
		doc = frappe.get_doc("Sales Shift Closing", closed["name"])
		self.assertAlmostEqual(doc.total_supplier_payments, 20, places=2)
		self.assertAlmostEqual(doc.total_purchases, 24, places=2)
		self.assertAlmostEqual(doc.net_difference, 0, places=2)
		refs = {(t.reference_doctype, t.reference_name) for t in doc.transactions}
		self.assertIn(("Purchase Order", order), refs)
		self.assertIn(("Purchase Order", credit), refs)
		self.assertIn(("Purchase Invoice", bill["invoice"]), refs)
		self.assertIn(("Payment Entry", bill["payment"]), refs)

		report = get_closing_report(closed["name"])
		self.assertEqual([p["name"] for p in report["supplier_payments"]], [bill["payment"]])
		self.assertNotIn(bill["payment"], [p["name"] for p in report["documents"]["payments"]])
		self.assertAlmostEqual(sum(c["amount"] for c in report["collections"]), paid_in, places=2)
		self.assertEqual({p["name"]: p["invoice"] for p in report["documents"]["purchases"]}, {order: bill["invoice"], credit: None})
		self.assertAlmostEqual(report["totals"]["total_supplier_payments"], 20, places=2)

	# ─── parent tests, not repeated here ───────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
