"""The Counter's Purchase screen: Purchase Orders keyed in like a sale.

The mirror of counter.py for buying. A cashier types a supplier, item codes and
quantities, submits the Purchase Order, and can turn it straight into a Purchase
Invoice that receives the stock into the profile's Main Warehouse, paid from the
drawer (a Pay Payment Entry the shift closing subtracts from that mode's expected
amount) or left on credit.

- search_suppliers() / search_purchase_items(): one query each for the boxes; an
  item's rate is the supplier's own buying price, then the price list's, then
  the item's last purchase rate.
- preview_counter_purchase(): ERPNext's totals for the cart, nothing saved.
- create_counter_purchase(): save the cart as a Purchase Order (a draft when it
  is held), else submit it.
- bill_counter_purchase(): Purchase Order -> Purchase Invoice (receiving the
  stock) -> Payment Entry, in one transaction.
- get_purchase_queue(): held orders, orders still to bill, today's bills.

Sales App User holds no buying permissions, so the writes go through
ignore_permissions after the caller is authorized here (can_counter_purchase,
and only their own documents unless they are a manager), the same pattern as
cash_movement.create_cash_movement().
"""

import json

import frappe
from frappe.utils import flt, nowdate

from sales_pwa.sales_app.utils import (
	_coerce_check,
	_default_company,
	_ensure_driver_mode_allowed,
	_get_driver_config,
	_is_manager,
	_require_capability,
	_require_van_user,
	_to_float,
)

SEARCH_LIMIT = 15
QUEUE_LIMIT = 50


def _require_purchase():
	"""Counter Sales staff whose profile allows purchases, and managers."""
	_require_van_user()
	_require_capability("can_counter_purchase", "raise purchase orders on the Counter")


def _company(config: dict | None) -> str:
	return (config or {}).get("company") or _default_company()


def _buying_price_list(config: dict | None) -> str | None:
	return (config or {}).get("buying_price_list") or frappe.db.get_single_value("Buying Settings", "buying_price_list") or None


def _receiving_warehouse(config: dict | None) -> str | None:
	"""The profile's Main Warehouse, else the company's default (a manager without a profile)."""
	from sales_pwa.sales_app.counter import _counter_warehouse

	return (config or {}).get("source_warehouse") or _counter_warehouse(config)


def _taxes_template(config: dict | None) -> str | None:
	return (config or {}).get("purchase_taxes_and_charges") or None


def _coerce_items(items) -> list[dict]:
	if isinstance(items, str):
		items = json.loads(items) if items.strip() else []
	return [row for row in (items or []) if isinstance(row, dict)]


def _check_own(doc):
	"""Staff work on their own purchases; a manager on anyone's."""
	user = frappe.session.user
	if doc.owner != user and user != "Administrator" and not _is_manager():
		frappe.throw(f"{doc.doctype} {doc.name} was raised by someone else.", frappe.PermissionError)


def _validate_supplier(supplier: str):
	if not supplier:
		frappe.throw("Pick a supplier.")
	row = frappe.db.get_value("Supplier", supplier, ["name", "disabled", "on_hold", "hold_type"], as_dict=True)
	if not row:
		frappe.throw(f"Supplier {supplier} does not exist.")
	if _coerce_check(row.disabled):
		frappe.throw(f"Supplier {supplier} is disabled.")


def _bill_no_required() -> bool:
	"""Whether this site makes the Supplier Invoice No mandatory on a Purchase Invoice
	(a Property Setter often does, to stop the same bill being entered twice)."""
	field = frappe.get_meta("Purchase Invoice").get_field("bill_no")
	return bool(field and field.reqd)


@frappe.whitelist()
def get_purchase_context():
	"""What the Purchase screen shows before anything is typed."""
	_require_purchase()
	config = _get_driver_config(required=False)
	return {
		"warehouse": _receiving_warehouse(config),
		"price_list": _buying_price_list(config),
		"taxes_and_charges": _taxes_template(config),
		"bill_no_required": _bill_no_required(),
	}


# ─── Search ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def search_suppliers(search: str | None = None, limit: int = 12):
	"""Suppliers for the supplier box: name, ID or mobile, those starting with the text first."""
	_require_purchase()
	text = (search or "").strip()
	limit = max(1, min(int(limit or 12), 50))
	params = {"like": f"%{text}%", "prefix": f"{text}%", "exact": text, "limit": limit}
	where = "s.disabled = 0"
	if text:
		where += " and (s.name like %(like)s or s.supplier_name like %(like)s or ifnull(s.mobile_no, '') like %(like)s)"
	rows = frappe.db.sql(
		f"""
		select s.name, s.supplier_name, s.supplier_group, s.mobile_no,
			case
				when s.name = %(exact)s then 0
				when s.supplier_name like %(prefix)s then 1
				when s.name like %(prefix)s then 1
				else 2
			end as rank
		from `tabSupplier` s
		where {where}
		order by rank asc, s.supplier_name asc
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)
	return [
		{"name": r.name, "supplier_name": r.supplier_name or r.name, "supplier_group": r.supplier_group, "mobile_no": r.mobile_no}
		for r in rows
	]


@frappe.whitelist()
def search_purchase_items(search: str | None = None, supplier: str | None = None, limit: int = SEARCH_LIMIT):
	"""Items for the Purchase screen's item box, in the shape the Counter's entry row
	takes (price_list_rate is the rate the line starts on).

	Matches code, name and barcode like the sale side. The rate is the supplier's own
	buying price, then the buying price list's, then the item's last purchase rate;
	stock is what the Main Warehouse holds now.
	"""
	_require_purchase()
	config = _get_driver_config(required=False)
	text = (search or "").strip()
	limit = max(1, min(int(limit or SEARCH_LIMIT), 50))
	price_list = _buying_price_list(config)
	warehouse = _receiving_warehouse(config)
	params = {
		"exact": text,
		"prefix": f"{text}%",
		"like": f"%{text}%",
		"price_list": price_list or "",
		"supplier": supplier or "",
		"warehouse": warehouse or "",
		"today": nowdate(),
		"limit": limit,
	}
	barcode_exact = "exists(select 1 from `tabItem Barcode` ib where ib.parent = item.name and ib.barcode = %(exact)s)"
	conditions = ["item.disabled = 0", "item.is_purchase_item = 1", "ifnull(item.has_variants, 0) = 0"]
	if text:
		conditions.append(
			"(item.name like %(like)s or item.item_name like %(like)s"
			" or exists(select 1 from `tabItem Barcode` ib where ib.parent = item.name and ib.barcode like %(like)s))"
		)
	rows = frappe.db.sql(
		f"""
		select
			item.name as item_code,
			item.item_name,
			item.item_group,
			item.stock_uom,
			item.is_stock_item,
			item.has_batch_no,
			item.has_serial_no,
			item.last_purchase_rate,
			ifnull(uom.must_be_whole_number, 0) as must_be_whole_number,
			(
				select ip.price_list_rate
				from `tabItem Price` ip
				where ip.item_code = item.name
					and ip.price_list = %(price_list)s
					and ip.buying = 1
					and ifnull(ip.uom, '') in ('', item.stock_uom)
					and ifnull(ip.supplier, '') in ('', %(supplier)s)
					and (ip.valid_from is null or ip.valid_from <= %(today)s)
					and (ip.valid_upto is null or ip.valid_upto >= %(today)s)
				order by ifnull(ip.supplier, '') desc, ip.uom desc, ip.valid_from desc
				limit 1
			) as price_list_rate,
			(
				select bin.actual_qty from `tabBin` bin
				where bin.item_code = item.name and bin.warehouse = %(warehouse)s
			) as actual_qty,
			case
				when item.name = %(exact)s then 0
				when {barcode_exact} then 0
				when item.name like %(prefix)s then 1
				when item.item_name like %(prefix)s then 2
				else 3
			end as rank
		from `tabItem` item
		left join `tabUOM` uom on uom.name = item.stock_uom
		where {" and ".join(conditions)}
		order by rank asc, item.item_name asc, item.name asc
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)
	items = []
	for row in rows:
		rate = row.price_list_rate if row.price_list_rate is not None else row.last_purchase_rate
		items.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"item_group": row.item_group,
				"stock_uom": row.stock_uom,
				"must_be_whole_number": _coerce_check(row.must_be_whole_number),
				"is_stock_item": _coerce_check(row.is_stock_item),
				"has_batch_no": _coerce_check(row.has_batch_no),
				"has_serial_no": _coerce_check(row.has_serial_no),
				"price_list_rate": _to_float(rate),
				"standard_rate": _to_float(row.last_purchase_rate),
				"actual_qty": _to_float(row.actual_qty) if warehouse else None,
				"exact": bool(text) and row.rank == 0,
			}
		)
	return {"items": items, "price_list": price_list, "warehouse": warehouse}


# ─── The order ────────────────────────────────────────────────────────────────

def _apply_purchase_payload(po, supplier: str, items, config: dict | None):
	"""Fill a (new or draft) Purchase Order from the cart. The typed rate stands:
	pricing rules are off, since the cashier keys in what the supplier charged."""
	_validate_supplier(supplier)
	rows = _coerce_items(items)
	if not rows:
		frappe.throw("Add at least one item.")
	today = nowdate()
	warehouse = _receiving_warehouse(config)
	if not warehouse:
		frappe.throw("No warehouse to receive into: set the Main Warehouse on your Sales Profile.")
	po.supplier = supplier
	po.company = _company(config)
	po.transaction_date = today
	po.schedule_date = today
	po.buying_price_list = _buying_price_list(config)
	po.set_warehouse = warehouse
	po.ignore_pricing_rule = 1
	po.set("items", [])
	for row in rows:
		item_code = row.get("item_code")
		qty = flt(row.get("qty"))
		rate = flt(row.get("rate"))
		if not item_code or qty <= 0:
			frappe.throw("Every line needs an item and a quantity above zero.")
		if rate < 0:
			frappe.throw(f"The rate of {item_code} cannot be negative.")
		if not frappe.db.get_value("Item", {"name": item_code, "disabled": 0, "is_purchase_item": 1}):
			frappe.throw(f"{item_code} is not an item you can buy.")
		po.append("items", {"item_code": item_code, "qty": qty, "rate": rate, "schedule_date": today, "warehouse": warehouse})

	template = _taxes_template(config)
	po.taxes_and_charges = template
	po.set("taxes", [])
	if template:
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		po.extend("taxes", get_taxes_and_charges("Purchase Taxes and Charges Template", template))
	# The caller is authorized already; ERPNext's party lookup would otherwise demand
	# read on Supplier, which Sales App User does not hold.
	po.flags.ignore_permissions = True
	po.run_method("set_missing_values")
	# set_missing_values fills the price list rate; put the typed rate back on top of it.
	for line, row in zip(po.items, rows):
		line.rate = flt(row.get("rate"))
		line.discount_percentage = 0
		line.discount_amount = 0
		line.margin_type = None
		line.margin_rate_or_amount = 0
	po.run_method("calculate_taxes_and_totals")
	return po


def _totals(po) -> dict:
	return {
		"lines": [
			{"item_code": r.item_code, "item_name": r.item_name, "qty": flt(r.qty), "uom": r.uom or r.stock_uom, "rate": flt(r.rate), "amount": flt(r.amount)}
			for r in po.items
		],
		"total_qty": flt(po.total_qty),
		"total": flt(po.total),
		"net_total": flt(po.net_total),
		"taxes": [
			{
				"description": r.description,
				"rate": flt(r.rate),
				"tax_amount": flt(r.tax_amount),
				"included_in_print_rate": _coerce_check(r.included_in_print_rate),
			}
			for r in po.taxes
		],
		"total_taxes_and_charges": flt(po.total_taxes_and_charges),
		"grand_total": flt(po.grand_total),
		"rounding_adjustment": flt(po.rounding_adjustment),
		"rounded_total": flt(po.rounded_total),
		"disable_rounded_total": _coerce_check(po.disable_rounded_total),
		"taxes_and_charges": po.taxes_and_charges or None,
	}


@frappe.whitelist()
def preview_counter_purchase(supplier: str, items):
	"""ERPNext's totals for the purchase cart as it stands. Nothing is saved; a cart
	ERPNext would refuse comes back as `error` rather than a failed request."""
	_require_purchase()
	config = _get_driver_config(required=False)
	try:
		po = _apply_purchase_payload(frappe.new_doc("Purchase Order"), supplier, items, config)
	except (frappe.ValidationError, frappe.PermissionError) as e:
		frappe.clear_messages()
		return {"error": str(e), "lines": [], "taxes": [], "total": 0.0, "grand_total": 0.0, "rounded_total": 0.0, "total_qty": 0.0,
			"warehouse": _receiving_warehouse(config), "price_list": _buying_price_list(config)}
	return {**_totals(po), "error": None, "warehouse": po.set_warehouse, "price_list": po.buying_price_list}


def _order_result(po) -> dict:
	return {
		"order": po.name,
		"docstatus": po.docstatus,
		"supplier": po.supplier,
		"supplier_name": po.supplier_name,
		"grand_total": flt(po.grand_total),
		"rounded_total": flt(po.rounded_total),
	}


@frappe.whitelist()
def create_counter_purchase(supplier: str, items, order_name: str | None = None, hold: int = 0):
	"""Save the cart as a Purchase Order: a draft when `hold`, else submitted.
	`order_name` is a held draft the cashier resumed; it is updated in place."""
	_require_purchase()
	config = _get_driver_config(required=False)
	if order_name:
		po = frappe.get_doc("Purchase Order", order_name)
		_check_own(po)
		if po.docstatus != 0:
			frappe.throw(f"{order_name} is already submitted.")
	else:
		po = frappe.new_doc("Purchase Order")
	_apply_purchase_payload(po, supplier, items, config)
	po.flags.ignore_permissions = True
	po.save()
	if not _coerce_check(hold):
		po.submit()
	return _order_result(po)


# ─── The bill ─────────────────────────────────────────────────────────────────

def _mode_account(mode_of_payment: str, company: str) -> str:
	account = frappe.db.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account")
	if not account:
		frappe.throw(f"No default account found for mode of payment {mode_of_payment} in company {company}")
	return account


def _pay_supplier(pi, mode_of_payment: str) -> str:
	"""A Pay Payment Entry for the whole bill, out of the mode's account."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Purchase Invoice", pi.name)
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = _mode_account(mode_of_payment, pi.company)
	pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency")
	if frappe.db.get_value("Account", pe.paid_from, "account_type") == "Bank":
		pe.reference_no = pi.bill_no or pi.name
		pe.reference_date = nowdate()
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe.name


@frappe.whitelist()
def bill_counter_purchase(
	order_name: str,
	mark_as_paid: int = 0,
	mode_of_payment: str | None = None,
	bill_no: str | None = None,
	bill_date: str | None = None,
):
	"""Purchase Order -> Purchase Invoice that receives the stock into the Main
	Warehouse, then (with `mark_as_paid`) a Payment Entry paying it in full from
	`mode_of_payment`. One transaction: a refused payment leaves no bill behind."""
	_require_purchase()
	mark_as_paid = _coerce_check(mark_as_paid)
	bill_no = (bill_no or "").strip() or None
	if not bill_no and _bill_no_required():
		frappe.throw("Enter the supplier's invoice number.", title="Supplier Invoice No")
	if mark_as_paid:
		if not mode_of_payment:
			frappe.throw("Select the mode of payment the supplier is paid with.")
		_ensure_driver_mode_allowed(mode_of_payment)
	config = _get_driver_config(required=False)

	po = frappe.get_doc("Purchase Order", order_name)
	_check_own(po)
	if po.docstatus != 1:
		frappe.throw(f"Submit {order_name} before you bill it.")
	if flt(po.per_billed) >= 100:
		frappe.throw(f"{order_name} is already billed.")

	from erpnext.buying.doctype.purchase_order.purchase_order import get_mapped_purchase_invoice

	pi = get_mapped_purchase_invoice(order_name, ignore_permissions=True)
	pi.update_stock = 1
	warehouse = _receiving_warehouse(config) or po.set_warehouse
	pi.set_warehouse = warehouse
	for row in pi.items:
		row.warehouse = row.warehouse or warehouse
	pi.bill_no = bill_no
	pi.bill_date = bill_date or (nowdate() if pi.bill_no else None)
	pi.flags.ignore_permissions = True
	pi.insert()
	pi.submit()

	payment = _pay_supplier(pi, mode_of_payment) if mark_as_paid else None
	pi.reload()
	return {
		"order": order_name,
		"invoice": pi.name,
		"supplier": pi.supplier,
		"supplier_name": pi.supplier_name,
		"grand_total": flt(pi.grand_total),
		"rounded_total": flt(pi.rounded_total),
		"outstanding_amount": flt(pi.outstanding_amount),
		"payment": payment,
	}


# ─── The side panel ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_purchase_queue():
	"""The cashier's own held Purchase Orders, submitted ones still to bill, and the
	bills they raised today."""
	_require_purchase()
	user = frappe.session.user
	fields = ["name", "supplier", "supplier_name", "transaction_date", "grand_total", "total_qty", "status", "creation", "modified"]
	held = frappe.get_all(
		"Purchase Order", filters={"owner": user, "docstatus": 0}, fields=fields, order_by="modified desc", limit_page_length=QUEUE_LIMIT
	)
	to_bill = frappe.get_all(
		"Purchase Order",
		filters={"owner": user, "docstatus": 1, "per_billed": ["<", 100], "status": ["not in", ["Closed", "Completed", "Cancelled", "On Hold"]]},
		fields=fields,
		order_by="creation desc",
		limit_page_length=QUEUE_LIMIT,
	)
	bills = frappe.get_all(
		"Purchase Invoice",
		filters={"owner": user, "docstatus": 1, "is_return": 0, "posting_date": nowdate()},
		fields=["name", "supplier", "supplier_name", "grand_total", "rounded_total", "outstanding_amount", "status", "creation"],
		order_by="creation desc",
		limit_page_length=QUEUE_LIMIT,
	)
	for rows in (held, to_bill):
		for row in rows:
			row["grand_total"] = flt(row.get("grand_total"))
			row["total_qty"] = flt(row.get("total_qty"))
	for row in bills:
		for field in ("grand_total", "rounded_total", "outstanding_amount"):
			row[field] = flt(row.get(field))
	return {"held": held, "to_bill": to_bill, "bills_today": bills}


@frappe.whitelist()
def get_counter_purchase(name: str):
	"""A held or submitted Purchase Order, to resume or bill it."""
	_require_purchase()
	po = frappe.get_doc("Purchase Order", name)
	_check_own(po)
	return {
		**_order_result(po),
		"per_billed": flt(po.per_billed),
		"items": [
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"qty": flt(r.qty),
				"rate": flt(r.rate),
				"stock_uom": r.stock_uom,
				"uom": r.uom,
			}
			for r in po.items
		],
	}
