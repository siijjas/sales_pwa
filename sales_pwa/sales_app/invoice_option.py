"""Sales Invoice Options: the manager-maintained master of ways to raise an invoice
(naming series + tax template), and what each staff member may pick from.

The option master is shared; a Sales Profile lists the options its staff can use
and marks one default. Staff see their profile's list, managers without a profile
see every enabled option.
"""

import json

import frappe

from sales_pwa.sales_app.doctype.sales_invoice_option.sales_invoice_option import sales_invoice_naming_series
from sales_pwa.sales_app.utils import (
	_coerce_check,
	_get_driver_config,
	_manager_only,
	_require_van_user,
)

OPTION_FIELDS = ["name", "option_name", "naming_series", "taxes_and_charges", "company", "description", "disabled"]


def invoice_option_payload(row, is_default: bool = False) -> dict:
	return {
		"name": row.name,
		"option_name": row.option_name,
		"naming_series": row.naming_series,
		"taxes_and_charges": row.taxes_and_charges,
		"company": row.company,
		"description": row.description,
		"disabled": _coerce_check(row.disabled),
		"is_default": bool(is_default),
	}


def profile_invoice_options(doc) -> list[dict]:
	"""The enabled options a Sales Profile lists, in the profile's order, with the
	profile's default flag. Disabled options are dropped so staff never see them."""
	rows = [r for r in (doc.invoice_options or []) if r.invoice_option]
	if not rows:
		return []
	masters = {
		m.name: m
		for m in frappe.get_all(
			"Sales Invoice Option",
			filters={"name": ["in", [r.invoice_option for r in rows]], "disabled": 0},
			fields=OPTION_FIELDS,
		)
	}
	out = [invoice_option_payload(masters[r.invoice_option], r.is_default) for r in rows if r.invoice_option in masters]
	if out and not any(o["is_default"] for o in out):
		out[0]["is_default"] = True
	return out


def all_enabled_invoice_options() -> list[dict]:
	rows = frappe.get_all("Sales Invoice Option", filters={"disabled": 0}, fields=OPTION_FIELDS, order_by="option_name asc")
	return [invoice_option_payload(r) for r in rows]


def resolve_invoice_option(config: dict | None, invoice_option: str | None) -> dict | None:
	"""Which option an invoice is raised with.

	Staff are held to their profile's list (the client only names an option, the
	profile decides whether it is allowed). A manager without a profile may use any
	enabled option. With nothing named, the profile's default applies; a profile
	without options returns None and the invoice is raised the historical way.
	"""
	allowed = (config or {}).get("invoice_options") or []
	if invoice_option:
		match = next((o for o in allowed if o["name"] == invoice_option), None)
		if match:
			return match
		if config:
			frappe.throw(f"Invoice option '{invoice_option}' is not enabled on your Sales Profile.", frappe.PermissionError)
		row = frappe.db.get_value("Sales Invoice Option", {"name": invoice_option, "disabled": 0}, OPTION_FIELDS, as_dict=True)
		if not row:
			frappe.throw(f"Invoice option '{invoice_option}' does not exist or is disabled.")
		return invoice_option_payload(row)
	return next((o for o in allowed if o.get("is_default")), allowed[0] if allowed else None)


# ─── Staff-facing ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def list_invoice_options():
	"""What the current user may invoice with: the profile's options, or every
	enabled option for a manager without a profile."""
	_require_van_user()
	config = _get_driver_config(required=False)
	if config:
		return config.get("invoice_options") or []
	return all_enabled_invoice_options()


# ─── Manager CRUD ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def list_all_invoice_options():
	_manager_only()
	rows = frappe.get_all("Sales Invoice Option", fields=OPTION_FIELDS, order_by="option_name asc")
	return [invoice_option_payload(r) for r in rows]


@frappe.whitelist()
def get_invoice_option_choices():
	"""Pick-lists for the option editor."""
	_manager_only()
	return {
		"naming_series": sales_invoice_naming_series(),
		"tax_templates": frappe.get_all(
			"Sales Taxes and Charges Template",
			filters={"disabled": 0},
			fields=["name", "company"],
			order_by="name asc",
			limit_page_length=200,
		),
		"companies": frappe.get_all("Company", fields=["name"], order_by="name asc", limit_page_length=50),
	}


@frappe.whitelist()
def save_invoice_option(payload):
	_manager_only()
	data = payload if isinstance(payload, dict) else json.loads(payload)
	name = data.get("name")
	doc = frappe.get_doc("Sales Invoice Option", name) if name else frappe.new_doc("Sales Invoice Option")
	doc.option_name = (data.get("option_name") or "").strip()
	doc.naming_series = (data.get("naming_series") or "").strip()
	doc.taxes_and_charges = data.get("taxes_and_charges") or None
	doc.company = data.get("company") or None
	doc.description = data.get("description") or None
	doc.disabled = 1 if _coerce_check(data.get("disabled")) else 0
	doc.flags.ignore_permissions = True
	doc.save()
	return invoice_option_payload(doc)


@frappe.whitelist()
def delete_invoice_option(name: str):
	_manager_only()
	used_by = frappe.get_all(
		"Sales Profile Invoice Option",
		filters={"invoice_option": name, "parenttype": "Sales Profile"},
		pluck="parent",
		distinct=True,
	)
	if used_by:
		frappe.throw(f"Invoice option {name} is used by Sales Profile(s): {', '.join(used_by)}. Remove it there first.")
	frappe.delete_doc("Sales Invoice Option", name, ignore_permissions=True)
	return {"deleted": name}
