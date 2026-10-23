"""Correcting the mode of payment of a submitted collection.

Run with: bench run-tests --site <site> --module sales_pwa.sales_app.tests.test_payment_mode_change
"""

import frappe
from frappe.utils import flt

from sales_pwa.sales_app.finance import change_payment_mode
from sales_pwa.sales_app.sales import create_sales_invoice, create_sales_order, submit_sales_order
from sales_pwa.sales_app.tests import test_shift_and_access as base
from sales_pwa.sales_app.utils import _driver_cache_key

TEST_PREFIX = base.TEST_PREFIX


class TestPaymentModeChange(base.TestShiftAndAccessRegressions):
	"""Reuses the shift tests' driver / Sales Profile / customer / item fixtures; the
	parent's own tests are blanked out below so they don't run twice."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# A second cash-type mode on the same drawer account, allowed on the profile.
		cls.card_mode = f"{TEST_PREFIX} Card"
		if not frappe.db.exists("Mode of Payment", cls.card_mode):
			frappe.get_doc(
				{
					"doctype": "Mode of Payment",
					"mode_of_payment": cls.card_mode,
					"type": "Cash",
					"enabled": 1,
					"accounts": [{"company": cls.company, "default_account": cls.ho_cash_account}],
				}
			).insert(ignore_permissions=True)
		profile = frappe.get_doc("Sales Profile", cls.van_profile)
		if cls.card_mode not in [r.mode_of_payment for r in profile.allowed_payment_modes]:
			profile.append("allowed_payment_modes", {"mode_of_payment": cls.card_mode})
			profile.save(ignore_permissions=True)
		frappe.cache.delete_value(_driver_cache_key(cls.driver_user))

	def _paid_invoice(self):
		so = create_sales_order(self.customer_allowed, [{"item_code": self.item_code, "qty": 2, "rate": 10}])
		submit_sales_order(so["name"])
		invoice = create_sales_invoice(so["name"], mark_as_paid=1, mode_of_payment=self.cash_mode)
		pe = frappe.get_all(
			"Payment Entry Reference", filters={"reference_name": invoice, "docstatus": 1}, pluck="parent"
		)[0]
		return invoice, pe

	def test_mode_changes_through_an_amended_copy(self):
		invoice, pe = self._paid_invoice()
		old = frappe.get_doc("Payment Entry", pe)

		result = change_payment_mode(pe, self.card_mode)
		new = frappe.get_doc("Payment Entry", result["name"])
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 2)
		self.assertEqual(new.amended_from, pe)
		self.assertEqual(new.docstatus, 1)
		self.assertEqual(new.mode_of_payment, self.card_mode)
		self.assertEqual(new.paid_to, self.ho_cash_account)
		self.assertEqual(flt(new.paid_amount), flt(old.paid_amount))
		self.assertEqual(new.posting_date, old.posting_date)
		self.assertEqual([(r.reference_name, flt(r.allocated_amount)) for r in new.references], [(invoice, 20.0)])
		# Shift attribution: same owner and creation as the original.
		self.assertEqual(new.owner, old.owner)
		self.assertEqual(str(new.creation), str(old.creation))
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")), 0)

		# The shift that took the payment now counts it under the new mode.
		from frappe.utils import add_to_date

		from sales_pwa.sales_app.shift import _collections_by_mode, _shift_payment_entries

		window = (add_to_date(old.creation, seconds=-1), add_to_date(old.creation, seconds=1))
		by_mode = _collections_by_mode(_shift_payment_entries(old.owner, *window))
		self.assertEqual(by_mode.get(self.card_mode), 20)
		self.assertNotIn(self.cash_mode, by_mode)

	def test_same_mode_is_refused(self):
		_, pe = self._paid_invoice()
		with self.assertRaisesRegex(frappe.ValidationError, "already recorded"):
			change_payment_mode(pe, self.cash_mode)

	def test_mode_outside_the_profile_is_refused(self):
		_, pe = self._paid_invoice()
		frappe.set_user("Administrator")
		other = f"{TEST_PREFIX} Not Allowed"
		if not frappe.db.exists("Mode of Payment", other):
			frappe.get_doc(
				{
					"doctype": "Mode of Payment",
					"mode_of_payment": other,
					"type": "Cash",
					"enabled": 1,
					"accounts": [{"company": self.company, "default_account": self.ho_cash_account}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(self.driver_user)
		with self.assertRaisesRegex(frappe.ValidationError, "not allowed"):
			change_payment_mode(pe, other)

	def test_payment_in_a_closed_shift_is_refused(self):
		_, pe = self._paid_invoice()
		frappe.set_user("Administrator")
		closing = frappe.new_doc("Sales Shift Closing")
		closing.append("transactions", {"reference_doctype": "Payment Entry", "reference_name": pe, "amount": 20})
		closing.db_insert()
		for row in closing.transactions:
			row.parent, row.parenttype, row.parentfield = closing.name, "Sales Shift Closing", "transactions"
			row.db_insert()
		frappe.db.set_value("Sales Shift Closing", closing.name, "docstatus", 1, update_modified=False)
		frappe.set_user(self.driver_user)
		with self.assertRaisesRegex(frappe.ValidationError, "closed shift"):
			change_payment_mode(pe, self.card_mode)

	def test_someone_elses_payment_is_refused(self):
		_, pe = self._paid_invoice()
		frappe.db.set_value("Payment Entry", pe, "owner", "Administrator", update_modified=False)
		with self.assertRaises(frappe.PermissionError):
			change_payment_mode(pe, self.card_mode)

	# ─── parent's tests are not re-run here ────────────────────────────────

	def test_driver_cannot_write_sales_order_through_docperms(self):
		pass

	def test_customer_access_respects_allowed_customer_groups(self):
		pass

	def test_driver_can_run_full_shift_and_sales_cycle(self):
		pass
