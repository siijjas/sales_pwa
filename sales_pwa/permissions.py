import frappe

# Single source of truth for who counts as a manager — utils._is_manager is the same
# check the whitelisted endpoints gate on, and the two drifting apart would mean the
# desk/REST layer and the app layer disagreed about who may see what.
from sales_pwa.sales_app.utils import (  # noqa: F401
	MANAGER_ROLES,
	_customer_access_error,
	_driver_customer_scope,
	_driver_warehouses,
	_get_driver_config,
	_is_manager,
)

DRIVER_ROLE = "Sales App User"


# ─── Sales EOD Report ────────────────────────────────────────────────────────────

def get_van_eod_report_permission_query_conditions(user: str | None = None):
	"""Row-level filter: drivers see only their own EOD reports; managers see all."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return None
	return f"`tabSales EOD Report`.`driver` = {frappe.db.escape(current_user)}"


def has_van_eod_report_permission(doc, ptype="read", user: str | None = None):
	"""Document-level check: drivers may create/submit/read/print their own EOD reports."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return True
	if ptype == "create":
		return True
	if ptype in {"read", "select", "print", "email", "submit"}:
		return getattr(doc, "driver", None) == current_user
	# write, delete, cancel → denied for drivers
	return False


# ─── Sales Expense Log ──────────────────────────────────────────────────────────

def get_van_expense_log_permission_query_conditions(user: str | None = None):
	"""Row-level filter: drivers see only their own expense logs; managers see all."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return None
	return f"`tabSales Expense Log`.`driver` = {frappe.db.escape(current_user)}"


def has_van_expense_log_permission(doc, ptype="read", user: str | None = None):
	"""Document-level check: drivers may only read their own legacy expense logs.

	New expenses are Van Cash Movements (see cash_movement.py); the log is history."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return True
	if ptype in {"read", "select", "print", "email"}:
		return getattr(doc, "driver", None) == current_user
	return False


# ─── Sales Shift Opening / Closing ───────────────────────────────────────────────

def _shift_query_conditions(doctype: str, user: str | None = None):
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return None
	return f"`tab{doctype}`.`driver` = {frappe.db.escape(current_user)}"


def _has_shift_permission(doc, ptype, user):
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return True
	if ptype == "create":
		return True
	if ptype in {"read", "select", "print", "email", "submit"}:
		return getattr(doc, "driver", None) == current_user
	if ptype == "write":
		# Defense in depth only, as things stand: the Sales App User role holds just
		# "read" on the shift doctypes, and shift.py creates/submits them with
		# flags.ignore_permissions, so this branch cannot currently grant anything —
		# has_controller_permissions() is a gate, and the role DocPerm is the binding
		# constraint. It is kept so that widening those DocPerms can never hand a
		# driver write access to someone else's shift, or to their own closed one.
		# `doc.docstatus` is already flipped to the TARGET value (1) by _submit()
		# before this check runs, so it cannot be used to detect "still a draft" —
		# check what is actually persisted in the DB instead.
		if getattr(doc, "driver", None) != current_user:
			return False
		if doc.is_new():
			return True
		return frappe.db.get_value(doc.doctype, doc.name, "docstatus") == 0
	# delete, cancel → denied for drivers
	return False


def get_van_shift_opening_permission_query_conditions(user: str | None = None):
	"""Row-level filter: drivers see only their own opening shifts; managers see all."""
	return _shift_query_conditions("Sales Shift Opening", user)


def has_van_shift_opening_permission(doc, ptype="read", user: str | None = None):
	"""Document-level check: drivers may create/submit/read/print their own opening shifts."""
	return _has_shift_permission(doc, ptype, user)


def get_van_shift_closing_permission_query_conditions(user: str | None = None):
	"""Row-level filter: drivers see only their own closing shifts; managers see all."""
	return _shift_query_conditions("Sales Shift Closing", user)


def has_van_shift_closing_permission(doc, ptype="read", user: str | None = None):
	"""Document-level check: drivers may create/submit/read/print their own closing shifts."""
	return _has_shift_permission(doc, ptype, user)


# ─── Sales Cash Movement ─────────────────────────────────────────────────────────

def get_van_cash_movement_permission_query_conditions(user: str | None = None):
	"""Row-level filter: drivers see only their own cash movements; managers see all."""
	return _shift_query_conditions("Sales Cash Movement", user)


def has_van_cash_movement_permission(doc, ptype="read", user: str | None = None):
	"""Drivers read their own; everything else goes through cash_movement.py with
	ignore_permissions after its own checks (cancel is manager-only there too)."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return True
	if ptype in {"read", "select", "print", "email"}:
		return getattr(doc, "driver", None) == current_user
	return False


# ─── Sales Profile ───────────────────────────────────────────────────────────────

def get_van_profile_permission_query_conditions(user: str | None = None):
	"""Row-level filter: managers see all Sales Profiles; drivers only see profiles they are assigned to."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return None
	# Driver can read only profiles where they appear in the assigned_drivers child
	# table. parenttype/parentfield are pinned because `parent` alone is not unique
	# across doctypes — another doctype's child row could carry a Sales Profile's name.
	return (
		f"`tabSales Profile`.`name` in ("
		f"  select `parent` from `tabSales Profile Driver`"
		f"  where `driver_user` = {frappe.db.escape(current_user)}"
		f"    and `parenttype` = 'Sales Profile'"
		f"    and `parentfield` = 'assigned_drivers'"
		f")"
	)


def has_van_profile_permission(doc, ptype="read", user: str | None = None):
	"""Document-level check: managers have full access; drivers can only read assigned profiles."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return True
	# Drivers: read-only, and only if they are in the assigned_drivers table.
	if ptype not in {"read", "select", "print", "email"}:
		return False
	# frappe.db.exists() rather than frappe.get_all(): this runs *inside* the
	# permission system, and a permission-checked read of the child doctype from here
	# re-enters it. Raw DB access keeps the check from recursing.
	return bool(
		frappe.db.exists(
			"Sales Profile Driver",
			{
				"parent": doc.name,
				"parenttype": "Sales Profile",
				"parentfield": "assigned_drivers",
				"driver_user": current_user,
			},
		)
	)


# ─── ERPNext doctypes the role reads through /api/resource ───────────────────────
#
# setup.py grants Sales App User plain read on Customer, Sales Order, Sales Invoice,
# Payment Entry, Item Price and Bin so the app's own list screens can query them. A
# role-level read is company-wide, so without these hooks any staff member could pull
# every customer, invoice and collection straight from the REST API, however the app
# itself scoped them. The hooks below apply the Sales Profile's scope (the same
# delivery route / customer groups utils._validate_customer_access enforces, the
# profile's warehouses, selling prices only) to list queries and single-document
# reads alike, so the REST layer shows a driver exactly what the endpoints would.
#
# Only users holding the driver role who are neither Administrator nor a manager are
# affected; everyone else gets None, which leaves Frappe's own answer untouched. A
# role holder with no active profile sees nothing: the role is revoked when the last
# profile goes, so that state is transient.

_NO_ROWS = "1=0"


def _scoped_config(user: str | None):
	"""(restricted, config): restricted is False for users these hooks leave alone;
	config is None for a role holder without an active profile."""
	current_user = user or frappe.session.user
	if current_user == "Administrator" or _is_manager(current_user):
		return False, None
	if DRIVER_ROLE not in frappe.get_roles(current_user):
		return False, None
	return True, _get_driver_config(user=current_user, required=False)


def _sql_list(values) -> str:
	return ", ".join(frappe.db.escape(v) for v in values)


def _customer_scope_sql(config, table: str = "`tabCustomer`") -> str | None:
	"""SQL confining `table` (a Customer row) to the profile's route and groups; None = unrestricted."""
	territories, groups = _driver_customer_scope(config)
	parts = []
	if territories is not None:
		parts.append(f"(ifnull({table}.`territory`, '') = '' or {table}.`territory` in ({_sql_list(territories)}))")
	if groups is not None:
		parts.append(f"(ifnull({table}.`customer_group`, '') = '' or {table}.`customer_group` in ({_sql_list(groups)}))")
	return " and ".join(parts) or None


def _customer_subquery(config) -> str | None:
	scope = _customer_scope_sql(config)
	if not scope:
		return None
	return f"(select `name` from `tabCustomer` where {scope})"


def _query_conditions(user, build):
	restricted, config = _scoped_config(user)
	if not restricted:
		return None
	if config is None:
		return _NO_ROWS
	return build(config)


def _doc_permission(user, allowed):
	"""None (defer to Frappe) unless the user is scoped and the document falls outside it."""
	restricted, config = _scoped_config(user)
	if not restricted:
		return None
	if config is None or not allowed(config):
		return False
	return None


def get_customer_permission_query_conditions(user: str | None = None):
	return _query_conditions(user, _customer_scope_sql)


def has_customer_permission(doc, ptype="read", user: str | None = None):
	return _doc_permission(user, lambda config: not _customer_access_error(config, doc.name))


def _customer_document_conditions(doctype: str):
	def build(config):
		customers = _customer_subquery(config)
		return f"`tab{doctype}`.`customer` in {customers}" if customers else None

	return lambda user=None: _query_conditions(user, build)


def _customer_document_permission(doc, user):
	return _doc_permission(
		user, lambda config: bool(doc.get("customer")) and not _customer_access_error(config, doc.customer)
	)


get_sales_order_permission_query_conditions = _customer_document_conditions("Sales Order")
get_sales_invoice_permission_query_conditions = _customer_document_conditions("Sales Invoice")


def has_sales_order_permission(doc, ptype="read", user: str | None = None):
	return _customer_document_permission(doc, user)


def has_sales_invoice_permission(doc, ptype="read", user: str | None = None):
	return _customer_document_permission(doc, user)


def get_payment_entry_permission_query_conditions(user: str | None = None):
	def build(config):
		customers = _customer_subquery(config)
		party = f"`tabPayment Entry`.`party` in {customers}" if customers else "1=1"
		return f"(`tabPayment Entry`.`party_type` = 'Customer' and {party})"

	return _query_conditions(user, build)


def has_payment_entry_permission(doc, ptype="read", user: str | None = None):
	return _doc_permission(
		user,
		lambda config: doc.get("party_type") == "Customer"
		and bool(doc.get("party"))
		and not _customer_access_error(config, doc.party),
	)


def get_item_price_permission_query_conditions(user: str | None = None):
	"""Staff price from selling lists only; buying prices are the company's cost."""
	return _query_conditions(user, lambda config: "`tabItem Price`.`selling` = 1")


def has_item_price_permission(doc, ptype="read", user: str | None = None):
	return _doc_permission(user, lambda config: bool(doc.get("selling")))


def get_bin_permission_query_conditions(user: str | None = None):
	def build(config):
		warehouses = _driver_warehouses(config)
		return f"`tabBin`.`warehouse` in ({_sql_list(warehouses)})" if warehouses else _NO_ROWS

	return _query_conditions(user, build)


def has_bin_permission(doc, ptype="read", user: str | None = None):
	return _doc_permission(user, lambda config: doc.get("warehouse") in _driver_warehouses(config))
