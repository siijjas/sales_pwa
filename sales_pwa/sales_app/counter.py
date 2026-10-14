"""The Counter: fast keyboard order entry on a PC for Counter Sales profiles.

The phone's Sell flow is three screens and, for the catalog, four REST calls per
keystroke (Item, Item Price, Bin, UOM). A cashier typing codes and quantities
needs one screen and one round trip per action. This module is the server side
of that screen; every write reuses the Sales Order / Sales Invoice helpers the
phone flow uses, so every Sales Profile rule (prices, rate and discount
controls, customer scope, shifts, invoice options, stock) applies unchanged.

- search_counter_items(): one query for code, name, barcode, price from the
  resolved price list, stock in the selling warehouse and the UOM rule, ranked so
  what the cashier is most likely typing comes first.
- preview_counter_totals(): what ERPNext would put on the order (re-taxed to the
  invoice option when one applies) for the cart as it stands, plus the stock
  shortages and the proposed invoice number. Nothing is saved.
- create_counter_sale(): order -> submit -> (invoice -> payment) in one request
  and one transaction. A failure anywhere rolls the whole sale back.
- get_counter_queue(): the cashier's held (draft) orders, submitted orders not
  yet invoiced, and today's invoices, for the side panel.
"""

import frappe
from frappe.utils import flt, nowdate

from sales_pwa.sales_app.invoice_option import resolve_invoice_option
from sales_pwa.sales_app.sales import (
	_apply_order_payload,
	_proposed_invoice_name,
	_resolve_price_list,
	_van_stock_shortages,
	create_sales_invoice,
	create_sales_order,
	submit_sales_order,
	update_sales_order,
)
from sales_pwa.sales_app.utils import (
	_coerce_check,
	_default_company,
	_ensure_driver_mode_allowed,
	_get_driver_config,
	_require_capability,
	_require_van_user,
	_selling_warehouse,
	_to_float,
	_validate_customer_access,
)

SEARCH_LIMIT = 15


def _require_counter():
	"""Counter Sales staff and managers only (see utils._capabilities)."""
	_require_van_user()
	_require_capability("can_counter_sell", "use the Counter screen")


def _counter_price_list(config: dict | None, customer: str | None) -> str | None:
	"""The profile's list (or the customer's own, per the profile); a manager without
	a profile prices from the company-wide default so the catalog is never blank."""
	price_list = _resolve_price_list(config, customer)
	if price_list or config:
		return price_list
	return frappe.db.get_single_value("Selling Settings", "selling_price_list") or None


def _counter_warehouse(config: dict | None) -> str | None:
	"""Where the counter sells from: the profile's Main Warehouse. A manager without a
	profile reads stock from the company default so the stock column still means
	something; their invoices fall back to ERPNext's own default the way they always did."""
	warehouse = _selling_warehouse(config)
	if warehouse or config:
		return warehouse
	company = _default_company()
	if company:
		try:
			warehouse = frappe.get_cached_value("Company", company, "default_warehouse")
		except Exception:
			warehouse = None
	return warehouse or frappe.db.get_single_value("Stock Settings", "default_warehouse") or None


@frappe.whitelist()
def search_counter_items(search: str | None = None, customer: str | None = None, limit: int = SEARCH_LIMIT):
	"""Items for the Counter's item box, with everything the entry row needs.

	Matches item code, item name and barcode. An exact code or barcode match ranks
	first and is flagged `exact`, so the client can add it on Enter without opening
	the list; then codes that start with the text, then names that start with it,
	then anything containing it. Price comes from the price list the order will be
	priced with (falling back to Item.standard_rate, as the order itself does),
	stock from the selling warehouse.
	"""
	_require_counter()
	config = _get_driver_config(required=False)
	if customer:
		_validate_customer_access(customer)
	text = (search or "").strip()
	limit = max(1, min(int(limit or SEARCH_LIMIT), 50))
	price_list = _counter_price_list(config, customer)
	warehouse = _counter_warehouse(config)

	params = {
		"exact": text,
		"prefix": f"{text}%",
		"like": f"%{text}%",
		"price_list": price_list or "",
		"warehouse": warehouse or "",
		"today": nowdate(),
		"limit": limit,
	}
	barcode_exact = "exists(select 1 from `tabItem Barcode` ib where ib.parent = item.name and ib.barcode = %(exact)s)"
	conditions = ["item.disabled = 0", "item.is_sales_item = 1", "ifnull(item.has_variants, 0) = 0"]
	if text:
		conditions.append(
			"(item.name like %(like)s or item.item_name like %(like)s"
			" or exists(select 1 from `tabItem Barcode` ib where ib.parent = item.name and ib.barcode like %(like)s))"
		)
	having = ""
	if warehouse and config and _coerce_check(config.get("hide_unavailable_items")):
		having = "having ifnull(actual_qty, 0) > 0 or ifnull(item.is_stock_item, 0) = 0"

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
			item.standard_rate,
			ifnull(uom.must_be_whole_number, 0) as must_be_whole_number,
			(
				select ip.price_list_rate
				from `tabItem Price` ip
				where ip.item_code = item.name
					and ip.price_list = %(price_list)s
					and ip.selling = 1
					and ifnull(ip.uom, '') in ('', item.stock_uom)
					and ifnull(ip.customer, '') = ''
					and (ip.valid_from is null or ip.valid_from <= %(today)s)
					and (ip.valid_upto is null or ip.valid_upto >= %(today)s)
				order by ip.uom desc, ip.valid_from desc
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
		{having}
		order by rank asc, item.item_name asc, item.name asc
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)

	items = []
	for row in rows:
		rate = row.price_list_rate if row.price_list_rate is not None else row.standard_rate
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
				"standard_rate": _to_float(row.standard_rate),
				# None when the counter has no warehouse to read (a manager without a profile
				# and no company default): the client then shows no stock column.
				"actual_qty": _to_float(row.actual_qty) if warehouse else None,
				"exact": bool(text) and row.rank == 0,
			}
		)
	return {"items": items, "price_list": price_list, "warehouse": warehouse}


def _build_preview_order(customer: str, items, discount_percent, discount_amount, option: dict | None):
	"""The Sales Order the cart would save, in memory, re-taxed to the invoice option
	the way create_sales_invoice() re-taxes the real order (_align_order_taxes)."""
	so = frappe.new_doc("Sales Order")
	_apply_order_payload(so, customer, items, discount_percent, discount_amount)
	if option:
		template = option.get("taxes_and_charges") or None
		if (so.taxes_and_charges or None) != template or (not template and so.taxes):
			from erpnext.controllers.accounts_controller import get_taxes_and_charges

			so.taxes_and_charges = template
			so.set("taxes", [])
			if template:
				so.extend("taxes", get_taxes_and_charges("Sales Taxes and Charges Template", template))
			so.run_method("calculate_taxes_and_totals")
	return so


@frappe.whitelist()
def preview_counter_totals(
	customer: str,
	items,
	discount_percent: float = 0,
	discount_amount: float = 0,
	invoice_option: str | None = None,
	mark_as_paid: int = 0,
	mode_of_payment: str | None = None,
):
	"""The totals the cashier is about to confirm, computed by ERPNext for the cart
	as it stands: lines at the rate the order would carry, discount, each tax line,
	grand and rounded totals, the stock the warehouse is short of, and the number
	the invoice would most likely get. Read-only.

	A cart the profile would refuse (a rate change the profile forbids, a discount
	over the cap, a zero-rated line) comes back as `error` with zeroed totals rather
	than a failed request, so the screen can say so while the cashier types.
	"""
	_require_counter()
	_validate_customer_access(customer)
	config = _get_driver_config(required=False)
	mark_as_paid = _coerce_check(mark_as_paid)
	warehouse = _counter_warehouse(config)

	blank = {
		"customer": customer,
		"lines": [],
		"total_qty": 0.0,
		"total": 0.0,
		"net_total": 0.0,
		"discount_amount": 0.0,
		"taxes": [],
		"total_taxes_and_charges": 0.0,
		"grand_total": 0.0,
		"rounding_adjustment": 0.0,
		"rounded_total": 0.0,
		"disable_rounded_total": bool(config and _coerce_check(config.get("disable_rounded_total"))),
		"taxes_and_charges": None,
		"invoice_option": None,
		"proposed_invoice_name": None,
		"short_items": [],
		"allow_sale_without_stock": bool(config and _coerce_check(config.get("allow_sale_without_stock"))),
		"warehouse": warehouse,
		"error": None,
	}
	try:
		option = resolve_invoice_option(config, invoice_option or None, mark_as_paid, mode_of_payment or None)
		so = _build_preview_order(customer, items, discount_percent, discount_amount, option)
	except (frappe.ValidationError, frappe.PermissionError) as e:
		frappe.clear_messages()
		blank["error"] = str(e)
		return blank

	sinv = frappe.new_doc("Sales Invoice")
	sinv.company = so.company
	sinv.customer = so.customer
	sinv.posting_date = nowdate()
	if option:
		sinv.naming_series = option["naming_series"]

	return {
		**blank,
		"lines": [
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": flt(row.qty),
				"uom": row.uom or row.stock_uom,
				"rate": flt(row.rate),
				"amount": flt(row.amount),
			}
			for row in so.items
		],
		"total_qty": flt(so.total_qty),
		"total": flt(so.total),
		"net_total": flt(so.net_total),
		"discount_amount": flt(so.discount_amount),
		"taxes": [
			{
				"description": row.description,
				"rate": flt(row.rate),
				"tax_amount": flt(row.tax_amount),
				"included_in_print_rate": _coerce_check(row.included_in_print_rate),
			}
			for row in so.taxes
		],
		"total_taxes_and_charges": flt(so.total_taxes_and_charges),
		"grand_total": flt(so.grand_total),
		"rounding_adjustment": flt(so.rounding_adjustment),
		"rounded_total": flt(so.rounded_total),
		"taxes_and_charges": so.taxes_and_charges or None,
		"invoice_option": option,
		"proposed_invoice_name": _proposed_invoice_name(sinv),
		"short_items": _van_stock_shortages(so, warehouse),
	}


@frappe.whitelist()
def create_counter_sale(
	customer: str,
	items,
	discount_percent: float = 0,
	discount_amount: float = 0,
	order_name: str | None = None,
	invoice: int = 0,
	mark_as_paid: int = 0,
	mode_of_payment: str | None = None,
	invoice_option: str | None = None,
	allow_without_stock: int = 0,
):
	"""One keystroke, one request: save the cart as a Sales Order (updating the held
	draft `order_name` when the cashier resumed one), submit it, and with `invoice`
	raise the Sales Invoice (collecting payment when `mark_as_paid`) the way
	create_sales_invoice() does. Everything runs in one transaction, so a refused
	invoice leaves no submitted order behind.

	Stock: the invoice moves stock out of the Main Warehouse. When the warehouse is
	short, the sale is refused with the shortages named, unless the cashier confirmed
	selling without stock and the profile allows it (then the available quantity is
	delivered and the rest stays pending on the order, as on a van).
	"""
	_require_counter()
	invoice = _coerce_check(invoice)
	mark_as_paid = _coerce_check(mark_as_paid)
	allow_without_stock = _coerce_check(allow_without_stock)
	config = _get_driver_config(required=False)

	if invoice:
		# Checked before anything is written so the error names the real problem.
		_require_capability("can_invoice", "invoice orders")
		if not mark_as_paid:
			_require_capability("can_credit_sale", "raise an invoice without collecting payment")
		if mark_as_paid:
			if not mode_of_payment:
				frappe.throw("Select a mode of payment to collect this sale.")
			_ensure_driver_mode_allowed(mode_of_payment)
		resolve_invoice_option(config, invoice_option or None, mark_as_paid, mode_of_payment or None)

	if order_name:
		order = update_sales_order(order_name, customer, items, discount_percent, discount_amount)
	else:
		order = create_sales_order(customer, items, discount_percent, discount_amount)
	submitted = submit_sales_order(order["name"])

	result = {
		"order": submitted["name"],
		"customer": submitted["customer"],
		"customer_name": submitted.get("customer_name"),
		"order_grand_total": flt(submitted.get("grand_total")),
		"invoice": None,
		"grand_total": flt(submitted.get("grand_total")),
		"rounded_total": flt(submitted.get("rounded_total")),
		"outstanding_amount": None,
		"short_items": [],
	}
	if not invoice:
		return result

	so = frappe.get_doc("Sales Order", submitted["name"])
	warehouse = _selling_warehouse(config)
	short_items = _van_stock_shortages(so, warehouse)
	if short_items and not allow_without_stock:
		names = ", ".join(
			f"{row['item_name']} (need {flt(row['required_qty'])}, have {flt(row['available_qty'])} {row['stock_uom']})"
			for row in short_items
		)
		frappe.throw(f"Not enough stock in {warehouse}: {names}.", title="Stock shortage")

	invoice_name = create_sales_invoice(
		so.name,
		mark_as_paid=1 if mark_as_paid else 0,
		mode_of_payment=mode_of_payment or None,
		allow_without_stock=1 if (short_items and allow_without_stock) else 0,
		invoice_option=invoice_option or None,
	)
	sinv = frappe.db.get_value(
		"Sales Invoice", invoice_name, ["grand_total", "rounded_total", "outstanding_amount"], as_dict=True
	)
	result.update(
		{
			"invoice": invoice_name,
			"grand_total": flt(sinv.grand_total),
			"rounded_total": flt(sinv.rounded_total),
			"outstanding_amount": flt(sinv.outstanding_amount),
			"short_items": short_items,
		}
	)
	return result


QUEUE_LIMIT = 50


@frappe.whitelist()
def get_counter_queue():
	"""The side panel: the cashier's own held orders (drafts), submitted orders still
	to be invoiced, and the invoices they raised today. Own documents only, for a
	manager too: the panel is a worklist, not a report."""
	_require_counter()
	user = frappe.session.user
	order_fields = ["name", "customer", "customer_name", "transaction_date", "grand_total", "total_qty", "status", "creation", "modified"]
	held = frappe.get_all(
		"Sales Order",
		filters={"owner": user, "docstatus": 0},
		fields=order_fields,
		order_by="modified desc",
		limit_page_length=QUEUE_LIMIT,
	)
	to_invoice = frappe.get_all(
		"Sales Order",
		filters={
			"owner": user,
			"docstatus": 1,
			"per_billed": ["<", 100],
			"status": ["not in", ["Closed", "Completed", "Cancelled"]],
		},
		fields=order_fields,
		order_by="creation desc",
		limit_page_length=QUEUE_LIMIT,
	)
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"owner": user, "docstatus": 1, "is_return": 0, "posting_date": nowdate()},
		fields=["name", "customer", "customer_name", "grand_total", "rounded_total", "outstanding_amount", "status", "creation"],
		order_by="creation desc",
		limit_page_length=QUEUE_LIMIT,
	)
	for rows in (held, to_invoice):
		for row in rows:
			row["grand_total"] = flt(row.get("grand_total"))
			row["total_qty"] = flt(row.get("total_qty"))
	for row in invoices:
		for field in ("grand_total", "rounded_total", "outstanding_amount"):
			row[field] = flt(row.get(field))
	return {"held": held, "to_invoice": to_invoice, "invoices_today": invoices}
