import json
import frappe
from frappe.utils import flt
from sales_pwa.sales_app.shift import require_open_shift
from sales_pwa.sales_app.utils import (
	_ensure_driver_mode_allowed,
	_get_allowed_payment_modes,
	_default_company,
	_require_van_user,
	_validate_customer_access,
	_is_manager,
)


@frappe.whitelist()
def get_outstanding_invoices(customer: str):
	_require_van_user()
	_validate_customer_access(customer)
	return frappe.get_list(
		"Sales Invoice",
		filters={
			"customer": customer,
			"docstatus": 1,
			"outstanding_amount": [">", 0]
		},
		fields=["name", "posting_date", "grand_total", "outstanding_amount"],
		order_by="posting_date asc"
	)


@frappe.whitelist()
def get_payment_modes():
	_require_van_user()
	modes = frappe.get_list("Mode of Payment", filters={"enabled": 1}, fields=["name", "type"])
	allowed_modes = _get_allowed_payment_modes(user=frappe.session.user, all_modes=False)
	if allowed_modes is not None:
		modes = [mode for mode in modes if mode["name"] in allowed_modes]
	# Sort: Cash first, then alphabetically
	return sorted(modes, key=lambda x: (x["name"] != "Cash", x["name"]))


@frappe.whitelist()
def get_customer_summary(customer: str):
	_require_van_user()
	_validate_customer_access(customer)
	company = _default_company()

	# Outstanding balance
	outstanding = frappe.db.sql(
		"""
		select sum(debit - credit) as outstanding
		from `tabGL Entry`
		where party_type = 'Customer'
			and party = %s
			and company = %s
		""",
		(customer, company),
		as_dict=1
	)
	outstanding_balance = (outstanding and outstanding[0].outstanding) or 0.0

	# Last invoice
	last_invoice = frappe.db.sql(
		"""
		select name, posting_date, grand_total
		from `tabSales Invoice`
		where customer = %s
			and docstatus = 1
			and company = %s
		order by posting_date desc, creation desc
		limit 1
		""",
		(customer, company),
		as_dict=1
	)

	# Last payment
	last_payment = frappe.db.sql(
		"""
		select name, posting_date, paid_amount
		from `tabPayment Entry`
		where party_type = 'Customer'
			and party = %s
			and payment_type = 'Receive'
			and docstatus = 1
			and company = %s
		order by posting_date desc, creation desc
		limit 1
		""",
		(customer, company),
		as_dict=1
	)

	return {
		"outstanding_balance": outstanding_balance,
		"last_invoice": last_invoice[0] if last_invoice else None,
		"last_payment": last_payment[0] if last_payment else None
	}


def make_receive_payment_entry(
	customer: str,
	mode_of_payment: str,
	paid_amount: float,
	reference_rows: list[dict],
	company: str | None = None,
):
	"""Build, insert, and submit a customer "Receive" Payment Entry.

	Shared by create_payment_entry() (manual driver-entered collection against
	outstanding invoices) and create_sales_invoice()'s mark_as_paid path
	(collect payment for a brand-new invoice at the moment it's raised), so
	both go through the exact same account-resolution and submission logic.

	Payment Entry is a standard ERPNext financial doctype. Sales App User does
	not hold broad ERPNext accounts permissions, so this always inserts/submits
	with ignore_permissions=True — callers are responsible for authorizing the
	request first (_require_van_user(), _validate_customer_access(),
	_ensure_driver_mode_allowed()).
	"""
	company = company or _default_company()
	curr = frappe.get_cached_value("Company", company, "default_currency")
	paid_to = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
		"default_account"
	)
	if not paid_to:
		frappe.throw(
			f"No default account found for mode of payment {mode_of_payment} in company {company}"
		)

	from erpnext.accounts.party import get_party_account
	party_account = get_party_account("Customer", customer, company)

	pe = frappe.new_doc("Payment Entry")
	pe.flags.ignore_permissions = True
	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.party = customer
	pe.mode_of_payment = mode_of_payment
	pe.paid_amount = paid_amount
	pe.received_amount = paid_amount
	pe.target_exchange_rate = 1.0
	pe.company = company
	pe.paid_to = paid_to
	pe.paid_to_account_currency = frappe.db.get_value("Account", paid_to, "account_currency")
	pe.paid_from = party_account
	pe.paid_from_account_currency = (
		frappe.db.get_value("Account", party_account, "account_currency") or curr
	)

	for row in reference_rows:
		pe.append("references", row)

	pe.insert()
	pe.submit()
	return pe


@frappe.whitelist()
def create_payment_entry(
	customer: str,
	mode_of_payment: str,
	paid_amount: float,
	references: str,
	sales_order: str = None,
):
	_require_van_user()
	require_open_shift("collect a payment")
	_validate_customer_access(customer)
	# Enforce the per-driver payment mode allowlist
	_ensure_driver_mode_allowed(mode_of_payment)
	if flt(paid_amount) <= 0:
		frappe.throw("The amount collected must be greater than zero.")

	refs = json.loads(references)
	for ref in refs:
		if flt(ref.get("allocated_amount")) < 0:
			frappe.throw("An allocated amount cannot be negative.")
	company = _default_company()

	# Allocate to Sales Invoices
	reference_rows = [
		{
			"reference_doctype": "Sales Invoice",
			"reference_name": ref["name"],
			"total_amount": ref["grand_total"],
			"outstanding_amount": ref["outstanding_amount"],
			"allocated_amount": ref["allocated_amount"],
		}
		for ref in refs
	]

	# Link to Sales Order for advance payment. A Sales Order reference row's
	# "outstanding amount" isn't a real doctype field — it must be derived the
	# same way ERPNext's own Payment Entry form does (grand_total - advance_paid),
	# via the framework's own get_reference_details(), or the row is left with
	# outstanding_amount=0 and ERPNext's own row validation rejects ANY positive
	# allocated_amount with "Allocated Amount cannot be greater than outstanding
	# amount" — which is exactly the bug this fixes.
	#
	# outstanding_amount here is the order's *rounded* total (grand_total minus
	# any rounding adjustment) minus advance_paid — e.g. grand_total 12.5 with a
	# -0.5 rounding adjustment gives outstanding 12.0. A driver collecting the
	# order's unrounded grand_total (12.5) is legitimately allowed to — that's a
	# normal advance, not a mistake — but Payment Entry's own row validation
	# always enforces allocated_amount <= outstanding_amount, so the excess
	# can't be allocated to this Sales Order; it's left unallocated on the
	# Payment Entry instead (a standard ERPNext advance/credit on the customer).
	if sales_order:
		from erpnext.accounts.party import get_party_account
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

		party_account = get_party_account("Customer", customer, company)
		party_account_currency = frappe.db.get_value("Account", party_account, "account_currency")
		details = get_reference_details("Sales Order", sales_order, party_account_currency)

		allocated = min(flt(paid_amount), flt(details.outstanding_amount))
		if allocated <= 0:
			frappe.throw(f"Sales Order {sales_order} has no outstanding amount to allocate against.")

		reference_rows.append({
			"reference_doctype": "Sales Order",
			"reference_name": sales_order,
			"total_amount": details.total_amount,
			"outstanding_amount": details.outstanding_amount,
			"allocated_amount": allocated,
		})

	pe = make_receive_payment_entry(customer, mode_of_payment, paid_amount, reference_rows, company=company)
	return pe.name


def _closing_that_counted(payment_entry: str) -> str | None:
	"""The submitted shift closing whose reconciliation summed this payment, if any."""
	rows = frappe.db.sql(
		"""select c.name from `tabSales Shift Transaction` t
		join `tabSales Shift Closing` c on c.name = t.parent and c.docstatus = 1
		where t.parenttype = 'Sales Shift Closing' and t.reference_doctype = 'Payment Entry'
			and t.reference_name = %s
		limit 1""",
		(payment_entry,),
	)
	return rows[0][0] if rows else None


@frappe.whitelist()
def change_payment_mode(payment_entry: str, mode_of_payment: str):
	"""Correct the mode of payment of a submitted collection (or supplier payment) that
	was recorded under the wrong one, e.g. card keyed in as cash.

	A submitted Payment Entry's mode and account cannot change in place, so this does
	what ERPNext's Cancel and Amend does: the entry is cancelled and an amended copy
	(name-1, amended_from set) is submitted with the new mode and that mode's account,
	the same amount, date and allocations. Both happen in one transaction.

	Shifts attribute a payment to whoever created it, by its creation time (see
	shift.py), so the copy is given the original's owner and creation back. Otherwise a
	manager's correction would move the money onto the manager's shift, or a payment
	from earlier in the day onto a later window. The cancelled original and the
	Version log keep the record of who changed it.

	Refused once a submitted shift closing has counted the payment: that closing's cash
	count would no longer add up. A manager reopens the shift first.
	"""
	_require_van_user()
	old = frappe.get_doc("Payment Entry", payment_entry)
	if not _is_manager() and old.owner != frappe.session.user:
		frappe.throw("You can only change your own payments.", frappe.PermissionError)
	if old.docstatus != 1:
		frappe.throw("Only a submitted payment can have its mode changed.")
	if (old.payment_type, old.party_type) not in (("Receive", "Customer"), ("Pay", "Supplier")):
		frappe.throw("Only customer collections and supplier payments can be changed here.")
	if old.party_type == "Customer":
		_validate_customer_access(old.party)
	if not mode_of_payment or mode_of_payment == old.mode_of_payment:
		frappe.throw(f"{old.name} is already recorded as {old.mode_of_payment}.")
	if not frappe.db.get_value("Mode of Payment", mode_of_payment, "enabled"):
		frappe.throw(f"Mode of payment {mode_of_payment} is not available.")
	# The modes the payment's own drawer takes, also when a manager corrects it.
	_ensure_driver_mode_allowed(mode_of_payment, user=old.owner)
	closing = _closing_that_counted(old.name)
	if closing:
		frappe.throw(
			f"{old.name} was counted in the closed shift {closing}. Ask a manager to reopen that shift, then change the mode.",
			title="Shift already closed",
		)
	if old.get("clearance_date"):
		frappe.throw(f"{old.name} has been reconciled with the bank and cannot be changed.")

	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": old.company}, "default_account"
	)
	if not account:
		frappe.throw(f"No default account found for mode of payment {mode_of_payment} in company {old.company}")
	account_currency = frappe.db.get_value("Account", account, "account_currency")
	side = "paid_to" if old.payment_type == "Receive" else "paid_from"
	if account_currency != old.get(f"{side}_account_currency"):
		frappe.throw(f"{mode_of_payment} is in {account_currency}, but this payment is in {old.get(f'{side}_account_currency')}.")

	new = frappe.copy_doc(old)
	new.amended_from = old.name
	new.mode_of_payment = mode_of_payment
	new.set(side, account)
	new.set(f"{side}_account_currency", account_currency)
	# ERPNext requires a reference on bank payments; reuse the original's, as
	# counter_purchase._pay_supplier() does for a fresh one.
	if frappe.db.get_value("Account", account, "account_type") == "Bank" and not new.reference_no:
		new.reference_no = old.name
		new.reference_date = old.posting_date

	# Payment Entry is an ERPNext accounting doctype the Sales App User role holds no
	# rights on; the caller was authorized above, as in make_receive_payment_entry().
	old.flags.ignore_permissions = True
	old.cancel()
	new.flags.ignore_permissions = True
	new.insert()
	new.submit()
	frappe.db.set_value(
		"Payment Entry", new.name, {"owner": old.owner, "creation": old.creation}, update_modified=False
	)
	return {"name": new.name, "amended_from": old.name, "mode_of_payment": new.mode_of_payment}


@frappe.whitelist()
def get_customer_ledger(customer: str, from_date: str = None, to_date: str = None):
	_require_van_user()
	_validate_customer_access(customer)
	company = _default_company()

	filters = {
		"party_type": "Customer",
		"party": customer,
		"company": company,
		"is_cancelled": 0,
		"voucher_type": ["in", ["Sales Invoice", "Payment Entry", "Sales Order", "Journal Entry"]],
	}

	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]

	opening_balance = 0.0
	if from_date:
		before_filters = {
			"party_type": "Customer",
			"party": customer,
			"company": company,
			"is_cancelled": 0,
			"posting_date": ["<", from_date],
			"voucher_type": ["in", ["Sales Invoice", "Payment Entry", "Sales Order", "Journal Entry"]],
		}
		result = frappe.get_all(
			"GL Entry",
			filters=before_filters,
			fields=["sum(debit) as debit", "sum(credit) as credit"]
		)
		if result:
			opening_balance = (result[0].debit or 0.0) - (result[0].credit or 0.0)

	entries = frappe.get_all(
		"GL Entry",
		filters=filters,
		fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit", "account"],
		order_by="posting_date asc, creation asc"
	)

	return {
		"opening_balance": opening_balance,
		"entries": entries
	}

# Expenses used to be logged here as plain Sales Expense Log records (no accounting).
# New entries are Van Cash Movements (expense or deposit, posted to a Journal Entry):
# see sales_pwa.sales_app.cash_movement. Old logs stay readable and still count in
# shift and manager reports.
