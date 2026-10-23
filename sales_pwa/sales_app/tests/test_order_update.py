"""Changing a submitted, not yet invoiced order, and billing several of a customer's
orders on one invoice.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_order_update
"""

import frappe
from frappe.utils import flt

from sales_pwa.sales_app.sales import (
	create_sales_invoice,
	create_sales_order,
	get_invoiceable_orders,
	preview_sales_invoice,
	submit_sales_order,
	update_submitted_sales_order,
)
from sales_pwa.sales_app.tests import test_shift_and_access as base

TEST_PREFIX = base.TEST_PREFIX


class TestOrderUpdateAndGrouping(base.TestShiftAndAccessRegressions):
	"""Reuses the shift tests' driver / Sales Profile / customer / item fixtures; the
	parent's own tests are blanked out below so they don't run twice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.second_item = f"{TEST_PREFIX} Item Two"
		if not frappe.db.exists("Item", cls.second_item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.second_item,
					"item_name": cls.second_item,
					"item_group": frappe.db.get_value("Item", cls.item_code, "item_group"),
					"stock_uom": cls.uom,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 7,
				}
			).insert(ignore_permissions=True)
		cls.other_customer = cls._get_or_create_customer(f"{TEST_PREFIX} Customer Other", cls.group_allowed)

	def _submitted_order(self, customer=None, qty=2, rate=10):
		so = create_sales_order(customer or self.customer_allowed, [{"item_code": self.item_code, "qty": qty, "rate": rate}])
		submit_sales_order(so["name"])
		return so["name"]

	# ─── update a submitted order ──────────────────────────────────────────

	def test_quantities_and_items_change_in_place(self):
		name = self._submitted_order()
		first_row = frappe.get_doc("Sales Order", name).items[0].name

		updated = update_submitted_sales_order(
			name,
			[
				{"item_code": self.item_code, "qty": 5, "rate": 10},
				{"item_code": self.second_item, "qty": 1, "rate": 7},
			],
		)
		order = frappe.get_doc("Sales Order", name)
		self.assertEqual(updated["name"], name)
		self.assertEqual(order.docstatus, 1)
		self.assertEqual([r.item_code for r in order.items], [self.item_code, self.second_item])
		self.assertEqual(order.items[0].name, first_row, "the existing row is kept, not recreated")
		self.assertEqual(flt(order.items[0].qty), 5)
		self.assertEqual(flt(order.items[0].stock_qty), 5)
		self.assertEqual(flt(order.net_total), 57)
		self.assertEqual(
			sum(flt(r.payment_amount) for r in order.payment_schedule), flt(order.rounded_total or order.grand_total)
		)

		# Remove the first item.
		update_submitted_sales_order(name, [{"item_code": self.second_item, "qty": 3, "rate": 7}])
		order.reload()
		self.assertEqual([r.item_code for r in order.items], [self.second_item])
		self.assertEqual(order.items[0].idx, 1)
		self.assertEqual(flt(order.net_total), 21)
		self.assertFalse(frappe.db.exists("Sales Order Item", first_row))

	def test_reserved_stock_follows_the_change(self):
		frappe.set_user("Administrator")
		stock_item = f"{TEST_PREFIX} Stock Item"
		if not frappe.db.exists("Item", stock_item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": stock_item,
					"item_name": stock_item,
					"item_group": frappe.db.get_value("Item", self.item_code, "item_group"),
					"stock_uom": self.uom,
					"is_stock_item": 1,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		frappe.set_user(self.driver_user)

		def reserved():
			return flt(frappe.db.get_value("Bin", {"item_code": stock_item, "warehouse": self.van_warehouse}, "reserved_qty"))

		before = reserved()
		so = create_sales_order(
			self.customer_allowed,
			[{"item_code": self.item_code, "qty": 1, "rate": 10}, {"item_code": stock_item, "qty": 4, "rate": 10}],
		)
		submit_sales_order(so["name"])
		self.assertEqual(reserved() - before, 4)
		update_submitted_sales_order(
			so["name"], [{"item_code": self.item_code, "qty": 1, "rate": 10}, {"item_code": stock_item, "qty": 1, "rate": 10}]
		)
		self.assertEqual(reserved() - before, 1)
		update_submitted_sales_order(so["name"], [{"item_code": self.item_code, "qty": 1, "rate": 10}])
		self.assertEqual(reserved() - before, 0)

	def test_discount_can_change(self):
		name = self._submitted_order()
		profile = frappe.get_doc("Sales Profile", self.van_profile)
		if not profile.get("allow_discount_change"):
			frappe.set_user("Administrator")
			frappe.db.set_value("Sales Profile", self.van_profile, "allow_discount_change", 1)
			self._clear_driver_cache()
			frappe.set_user(self.driver_user)
		update_submitted_sales_order(name, [{"item_code": self.item_code, "qty": 2, "rate": 10}], discount_amount=5)
		self.assertEqual(flt(frappe.db.get_value("Sales Order", name, "grand_total")), 15)

	def test_invoiced_order_cannot_change(self):
		name = self._submitted_order()
		create_sales_invoice(name)
		with self.assertRaisesRegex(frappe.ValidationError, "already been invoiced"):
			update_submitted_sales_order(name, [{"item_code": self.item_code, "qty": 1, "rate": 10}])

	def test_draft_is_not_updated_here(self):
		so = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 1, "rate": 10}])
		with self.assertRaisesRegex(frappe.ValidationError, "Only a submitted sales order"):
			update_submitted_sales_order(so["name"], [{"item_code": self.item_code, "qty": 2, "rate": 10}])

	def test_rate_change_rule_still_applies(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Sales Profile", self.van_profile, "allow_rate_change", 0)
		self._clear_driver_cache()
		frappe.set_user(self.driver_user)
		name = self._submitted_order()
		# The second item has a catalog price (standard_rate 7) to hold the rate to.
		with self.assertRaises(frappe.PermissionError):
			update_submitted_sales_order(name, [{"item_code": self.second_item, "qty": 2, "rate": 1}])

	# ─── one invoice for several orders ────────────────────────────────────

	def test_orders_of_one_customer_share_an_invoice(self):
		first = self._submitted_order(qty=2)
		second = self._submitted_order(qty=3)
		listed = [row.name for row in get_invoiceable_orders(self.customer_allowed)]
		self.assertIn(first, listed)
		self.assertIn(second, listed)

		preview = preview_sales_invoice(first, other_orders=[second])
		self.assertEqual(preview["sales_orders"], [first, second])
		self.assertEqual(preview["net_total"], 50)

		name = create_sales_invoice(first, other_orders=frappe.as_json([second]))
		inv = frappe.get_doc("Sales Invoice", name)
		self.assertEqual({row.sales_order for row in inv.items}, {first, second})
		self.assertEqual(inv.grand_total, preview["grand_total"])
		for order in (first, second):
			self.assertEqual(flt(frappe.db.get_value("Sales Order", order, "per_billed")), 100)
		self.assertNotIn(first, [row.name for row in get_invoiceable_orders(self.customer_allowed)])

	def test_grouped_discounts_add_up(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Sales Profile", self.van_profile, "allow_discount_change", 1)
		self._clear_driver_cache()
		frappe.set_user(self.driver_user)
		first = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 2, "rate": 10}], discount_percent=10)
		submit_sales_order(first["name"])
		second = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 3, "rate": 10}], discount_amount=4)
		submit_sales_order(second["name"])
		preview = preview_sales_invoice(first["name"], other_orders=[second["name"]])
		self.assertEqual(preview["discount_amount"], 6)
		self.assertEqual(preview["grand_total"], 44)

	def test_another_customers_order_is_refused(self):
		first = self._submitted_order()
		other = self._submitted_order(customer=self.other_customer)
		with self.assertRaisesRegex(frappe.ValidationError, "Only one customer's orders"):
			preview_sales_invoice(first, other_orders=[other])

	def test_partly_invoiced_order_is_not_grouped(self):
		first = self._submitted_order()
		second = self._submitted_order()
		frappe.db.set_value("Sales Order", second, "per_billed", 50)
		with self.assertRaisesRegex(frappe.ValidationError, "partly invoiced"):
			create_sales_invoice(first, other_orders=[second])

	def test_delivered_order_is_not_grouped(self):
		first = self._submitted_order()
		second = self._submitted_order()
		frappe.db.set_value("Sales Order", second, "per_delivered", 100)
		self.assertNotIn(second, [row.name for row in get_invoiceable_orders(self.customer_allowed)])
		with self.assertRaisesRegex(frappe.ValidationError, "already been delivered"):
			preview_sales_invoice(first, other_orders=[second])

	def _clear_driver_cache(self):
		from sales_pwa.sales_app.utils import _driver_cache_key

		frappe.cache.delete_value(_driver_cache_key(self.driver_user))

	# ─── parent's tests are not re-run here ────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
