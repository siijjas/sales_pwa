import frappe

# Single source of truth for who counts as a manager — utils._is_manager is the same
# check the whitelisted endpoints gate on, and the two drifting apart would mean the
# desk/REST layer and the app layer disagreed about who may see what.
from sales_pwa.sales_app.utils import MANAGER_ROLES, _is_manager  # noqa: F401


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
