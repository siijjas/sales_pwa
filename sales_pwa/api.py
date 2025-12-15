import frappe
from frappe.utils import nowdate


def _default_naming_series():
	for field in frappe.get_meta("Sales Order").fields:
		if field.fieldname == "naming_series" and field.default:
			return field.default
	return "SO-"


def _default_company():
	return frappe.defaults.get_defaults().get("company") or frappe.db.get_default("company")


def _apply_defaults(doc):
	if not doc.company:
		doc.company = _default_company()
	if not doc.naming_series:
		doc.naming_series = _default_naming_series()
	if not doc.order_type:
		doc.order_type = "Sales"
	if not doc.transaction_date:
		doc.transaction_date = nowdate()
	if not doc.delivery_date:
		doc.delivery_date = doc.transaction_date


def _ensure_payment_schedule(doc):
	if doc.payment_schedule:
		return
	grand = doc.grand_total or doc.net_total or 0
	if not grand:
		return
	doc.append(
		"payment_schedule",
		{
			"due_date": doc.delivery_date or doc.transaction_date or nowdate(),
			"invoice_portion": 100,
			"payment_amount": grand,
			"base_payment_amount": grand,
			"description": "Full Payment",
		},
	)


@frappe.whitelist()
def submit_sales_order(name: str):
	doc = frappe.get_doc("Sales Order", name)
	_apply_defaults(doc)
	doc.run_method("set_missing_values")
	doc.run_method("calculate_taxes_and_totals")
	_ensure_payment_schedule(doc)
	doc.save()
	doc.submit()
	return doc.as_dict()
