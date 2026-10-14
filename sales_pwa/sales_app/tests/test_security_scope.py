"""Regression tests for the 2026-10-14 security audit fixes.

1. A credit note (create_sales_return) is held to the same price controls as an
   order, and to what the customer actually bought less what they already returned.
2. The Sales App User role's REST reads (Customer, Sales Invoice, Item Price, Bin)
   are scoped to the staff member's Sales Profile by sales_pwa.permissions, so
   /api/resource shows a driver no more than the app's endpoints do.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_security_scope
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from sales_pwa.sales_app.sales import create_sales_return

TEST_PREFIX = "_Test Sales App Scope"


def _root_group(doctype: str) -> str | None:
	return frappe.db.get_value(doctype, {"is_group": 1}, "name")


class TestSecurityScope(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company_row = frappe.get_all("Company", fields=["name"], limit=1)
		if not company_row:
			raise unittest.SkipTest("No Company configured on this site")
		cls.company = company_row[0].name

		item_group = _root_group("Item Group")
		# Customers need a leaf group; territories are created under the tree's root.
		customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		territory_root = _root_group("Territory")
		uom_row = frappe.get_all("UOM", limit=1)
		warehouses = frappe.get_all(
			"Warehouse", filters={"company": cls.company, "is_group": 0}, fields=["name"], limit=2
		)
		if not (item_group and customer_group and territory_root and uom_row) or len(warehouses) < 2:
			raise unittest.SkipTest("Item Group / Customer Group / Territory / UOM / two Warehouses missing")
		cls.warehouses = [w.name for w in warehouses]

		cls.route, cls.other_territory = f"{TEST_PREFIX} Route", f"{TEST_PREFIX} Elsewhere"
		for name in (cls.route, cls.other_territory):
			if not frappe.db.exists("Territory", name):
				frappe.get_doc(
					{"doctype": "Territory", "territory_name": name, "parent_territory": territory_root, "is_group": 0}
				).insert(ignore_permissions=True)

		cls.customer, cls.other_customer = f"{TEST_PREFIX} Customer", f"{TEST_PREFIX} Other Customer"
		for name, territory in ((cls.customer, cls.route), (cls.other_customer, cls.other_territory)):
			if not frappe.db.exists("Customer", name):
				frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": name,
						"customer_group": customer_group,
						"territory": territory,
						"customer_type": "Company",
					}
				).insert(ignore_permissions=True)

		cls.item_code = f"{TEST_PREFIX} Item"
		if not frappe.db.exists("Item", cls.item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.item_code,
					"item_name": cls.item_code,
					"item_group": item_group,
					"stock_uom": uom_row[0].name,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 100,
				}
			).insert(ignore_permissions=True)

		cls.driver = "_test_sales_app_scope_driver@example.com"
		if not frappe.db.exists("User", cls.driver):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.driver,
					"first_name": "Test Scope Driver",
					"user_type": "System User",
					"send_welcome_email": 0,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)

		cls.profile = f"{TEST_PREFIX} Profile"
		if not frappe.db.exists("Sales Profile", cls.profile):
			frappe.get_doc(
				{
					"doctype": "Sales Profile",
					"profile_name": cls.profile,
					"company": cls.company,
					"is_active": 1,
					"source_warehouse": cls.warehouses[0],
					"van_warehouse": cls.warehouses[1],
					"delivery_route": cls.route,
					"allow_rate_change": 0,
					"allow_return": 1,
					"require_open_shift": 0,
					"assigned_drivers": [{"driver_user": cls.driver}],
				}
			).insert(ignore_permissions=True)

		# The invoices below stand in for history: no order behind them. Selling
		# Settings may insist on one; the rollback at class end restores the setting.
		cls.so_required = frappe.db.get_single_value("Selling Settings", "so_required")
		frappe.db.set_single_value("Selling Settings", "so_required", "No")

		# What the customer bought: 2 units at 100 on a submitted invoice.
		cls.invoice = cls._invoice(cls.customer, 2)
		cls.other_invoice = cls._invoice(cls.other_customer, 1)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.set_single_value("Selling Settings", "so_required", cls.so_required or "No")

	@classmethod
	def _invoice(cls, customer: str, qty: float) -> str:
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": cls.company,
				"items": [{"item_code": cls.item_code, "qty": qty, "rate": 100}],
			}
		)
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()
		return si.name

	def _as_driver(self):
		frappe.set_user(self.driver)
		self.addCleanup(frappe.set_user, "Administrator")

	# ─── create_sales_return ────────────────────────────────────────────────────

	def test_return_rate_is_held_to_the_catalog(self):
		self._as_driver()
		with self.assertRaises(frappe.PermissionError):
			create_sales_return(self.customer, [{"item_code": self.item_code, "qty": 1, "rate": 999999}])

	def test_return_cannot_exceed_what_was_bought(self):
		self._as_driver()
		with self.assertRaises(frappe.PermissionError):
			create_sales_return(self.customer, [{"item_code": self.item_code, "qty": 3, "rate": 100}])

	def test_return_within_purchase_then_blocked_once_used_up(self):
		self._as_driver()
		name = create_sales_return(self.customer, [{"item_code": self.item_code, "qty": 1, "rate": 100}])
		si = frappe.get_doc("Sales Invoice", name)
		self.assertEqual(si.docstatus, 1)
		self.assertEqual(si.is_return, 1)
		self.assertAlmostEqual(si.grand_total, -100, places=2)
		# 2 bought, 1 returned: another 2 is one too many.
		with self.assertRaises(frappe.PermissionError):
			create_sales_return(self.customer, [{"item_code": self.item_code, "qty": 2, "rate": 100}])

	def test_return_blocked_for_customer_outside_route(self):
		self._as_driver()
		with self.assertRaises(frappe.PermissionError):
			create_sales_return(self.other_customer, [{"item_code": self.item_code, "qty": 1, "rate": 100}])

	# ─── REST scope ───────────────────────────────────────────────────────────────

	def test_customer_list_and_read_follow_the_route(self):
		self._as_driver()
		names = frappe.get_list("Customer", filters={"name": ["like", f"{TEST_PREFIX}%"]}, pluck="name")
		self.assertIn(self.customer, names)
		self.assertNotIn(self.other_customer, names)
		self.assertTrue(frappe.get_doc("Customer", self.customer).has_permission("read"))
		self.assertFalse(frappe.get_doc("Customer", self.other_customer).has_permission("read"))

	def test_invoice_list_and_read_follow_the_route(self):
		self._as_driver()
		names = frappe.get_list("Sales Invoice", filters={"customer": ["like", f"{TEST_PREFIX}%"]}, pluck="name")
		self.assertIn(self.invoice, names)
		self.assertNotIn(self.other_invoice, names)
		self.assertTrue(frappe.get_doc("Sales Invoice", self.invoice).has_permission("read"))
		self.assertFalse(frappe.get_doc("Sales Invoice", self.other_invoice).has_permission("read"))

	def test_buying_prices_are_hidden(self):
		price_list = frappe.db.get_value("Price List", {"buying": 1, "enabled": 1}, "name")
		if not price_list:
			raise unittest.SkipTest("No buying price list on this site")
		price = frappe.get_doc(
			{"doctype": "Item Price", "item_code": self.item_code, "price_list": price_list, "price_list_rate": 60}
		).insert(ignore_permissions=True)
		self._as_driver()
		self.assertNotIn(price.name, frappe.get_list("Item Price", filters={"item_code": self.item_code}, pluck="name"))
		# A fresh copy: the inserted object still carries ignore_permissions, which
		# Document.has_permission() honours before asking the hooks.
		self.assertFalse(frappe.get_doc("Item Price", price.name).has_permission("read"))

	def test_bins_limited_to_profile_warehouses(self):
		self._as_driver()
		elsewhere = frappe.get_list("Bin", filters={"warehouse": ["not in", self.warehouses]}, pluck="name", limit=5)
		self.assertEqual(elsewhere, [])

	def test_manager_is_not_scoped(self):
		frappe.set_user("Administrator")
		names = frappe.get_list("Customer", filters={"name": ["like", f"{TEST_PREFIX}%"]}, pluck="name")
		self.assertIn(self.other_customer, names)
