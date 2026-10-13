"""WhatsApp notifications for the Sales App.

Orders and customer payments are announced in one WhatsApp group through the
Baileys gateway that ships in the app's whatsapp-gateway/ folder (a linked
device for the company's WhatsApp number, reached over a local HTTP API).

Flow: doc_events (hooks.py) call on_document_event() → the event is parked in
frappe.local until the transaction commits (so a save followed by a submit in the
same request posts once, and nothing is posted for a rolled-back change) → the
message is built from the committed document and sent from a background job, so
a slow or dead gateway never slows down or fails the sale itself.

Adding a use case: write a `_<something>_message(doc, event, user)` builder,
list it in MESSAGE_BUILDERS, and hook the doctype's events in hooks.py.

Health: check_gateway_health() runs every minute from the scheduler, asks the
gateway for its state and records it on WhatsApp Settings (status, linked
number, last error), raising one Error Log entry when the link goes down.
"""

import requests

import frappe
from frappe.utils import cint, flt, fmt_money, format_datetime, get_fullname, now_datetime

SETTINGS = "WhatsApp Settings"
SALES_APP_PATH = "/api/method/sales_pwa."
MANAGER_ROLES = ("System Manager", "Sales Manager")

# doc_event method → human event name, per doctype
EVENTS = {
	"Sales Order": {
		"after_insert": "created",
		"on_update": "updated",
		"on_submit": "confirmed",
		"on_update_after_submit": "updated",
		"on_cancel": "cancelled",
	},
	"Payment Entry": {
		"on_submit": "received",
		"on_cancel": "cancelled",
	},
}

ORDER_HEADINGS = {
	"created": "🆕 New order",
	"updated": "✏️ Order updated",
	"confirmed": "✅ Order confirmed",
	"cancelled": "❌ Order cancelled",
}
PAYMENT_HEADINGS = {
	"received": "💰 Payment received",
	"cancelled": "↩️ Payment cancelled",
}


class GatewayError(Exception):
	"""The gateway could not be reached or refused the request."""


# Gateway /status "state" → the status shown on WhatsApp Settings.
STATUS_BY_STATE = {
	"connected": "Connected",
	"qr": "Not linked",
	"logged_out": "Not linked",
	"restricted": "Restricted",
}
# "connecting" or no answer at all is a failed check; this many in a row is Down.
FAILED_CHECKS_FOR_DOWN = 2
STATUS_FIELDS = ("status", "linked_number", "last_error", "failed_checks", "status_changed_at")


# ------------------------------------------------------------------ settings


def get_settings():
	return frappe.get_cached_doc(SETTINGS)


def _from_sales_app() -> bool:
	"""True while serving one of the app's own endpoints (the PWA's writes)."""
	request = getattr(frappe.local, "request", None)
	path = getattr(request, "path", "") or ""
	return path.startswith(SALES_APP_PATH)


def _wants(settings, doc) -> bool:
	if not settings.enabled or not settings.group_id:
		return False
	if doc.doctype == "Sales Order":
		return bool(settings.notify_orders)
	if doc.doctype == "Payment Entry":
		return bool(settings.notify_payments) and doc.payment_type == "Receive" and doc.party_type == "Customer"
	return False


# ---------------------------------------------------------------- doc events


def on_document_event(doc, method):
	"""hooks.py doc_events entry point for every doctype in EVENTS."""
	event = EVENTS.get(doc.doctype, {}).get(method)
	if not event:
		return
	# insert() runs on_update right after after_insert; "created" already covers it.
	if method == "on_update" and doc.flags.in_insert:
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
		return
	settings = get_settings()
	if not _wants(settings, doc):
		return
	if settings.only_sales_app and not _from_sales_app():
		return
	_queue(doc, event)


def _pending() -> dict:
	if not hasattr(frappe.local, "sales_pwa_whatsapp_pending"):
		frappe.local.sales_pwa_whatsapp_pending = {}
	return frappe.local.sales_pwa_whatsapp_pending


def _queue(doc, event: str):
	"""Park the event until commit. A later event for the same document in the
	same transaction replaces it, so save+submit posts "confirmed" only."""
	key = (doc.doctype, doc.name)
	_pending()[key] = {"event": event, "user": frappe.session.user}
	frappe.db.after_commit.add(lambda: _flush(key))


def _flush(key):
	entry = _pending().pop(key, None)
	if not entry:
		return  # already flushed by an earlier callback for the same document
	doctype, name = key
	try:
		doc = _load_doc(doctype, name)
		text = build_message(doc, entry["event"], entry["user"])
		if text:
			_dispatch(text)
	except Exception:
		# A notification must never break the request that triggered it.
		frappe.log_error(title="WhatsApp notification not queued", message=frappe.get_traceback())


def _load_doc(doctype: str, name: str):
	return frappe.get_doc(doctype, name)


def _dispatch(text: str):
	frappe.enqueue(
		"sales_pwa.sales_app.whatsapp.send_group_message",
		queue="short",
		timeout=60,
		text=text,
	)


# ------------------------------------------------------------------ messages


def build_message(doc, event: str, user: str | None = None) -> str | None:
	builder = MESSAGE_BUILDERS.get(doc.doctype)
	return builder(doc, event, user) if builder else None


def _order_message(doc, event: str, user: str | None) -> str:
	settings = get_settings()
	lines = [
		f"*{ORDER_HEADINGS.get(event, event.title())}* · {doc.name}",
		f"Customer: {doc.customer_name or doc.customer}",
		f"Staff: {_staff(user or doc.owner)}",
	]
	items = doc.get("items") or []
	if settings.include_items and items:
		limit = cint(settings.max_items) or len(items)
		lines.append(f"Items ({len(items)}):")
		for row in items[:limit]:
			lines.append(f"• {row.item_name or row.item_code} × {_qty(row.qty)} {row.uom or ''}".rstrip())
		if len(items) > limit:
			lines.append(f"… and {len(items) - limit} more")
	else:
		lines.append(f"Items: {len(items)} · {_qty(doc.total_qty)} units")
	if flt(doc.discount_amount):
		lines.append(f"Discount: {_money(doc.discount_amount, doc.currency)}")
	lines.append(f"Total: {_money(doc.grand_total, doc.currency)}")
	if event == "cancelled":
		lines.append("Status: Cancelled")
	elif doc.docstatus == 0:
		lines.append("Status: Draft, not yet confirmed")
	lines.append(_when(doc))
	return "\n".join(lines)


def _payment_message(doc, event: str, user: str | None) -> str:
	currency = doc.paid_from_account_currency or doc.paid_to_account_currency
	lines = [
		f"*{PAYMENT_HEADINGS.get(event, event.title())}* · {doc.name}",
		f"Customer: {doc.party_name or doc.party}",
		f"Amount: {_money(doc.paid_amount, currency)} · {doc.mode_of_payment or 'No mode'}",
	]
	refs = [r for r in (doc.get("references") or []) if flt(r.allocated_amount)]
	if refs:
		against = ", ".join(f"{r.reference_name} ({_money(r.allocated_amount, currency)})" for r in refs)
		lines.append(f"Against: {against}")
	if flt(doc.unallocated_amount):
		lines.append(f"Unallocated (advance): {_money(doc.unallocated_amount, currency)}")
	lines.append(f"Staff: {_staff(user or doc.owner)}")
	lines.append(_when(doc))
	return "\n".join(lines)


MESSAGE_BUILDERS = {
	"Sales Order": _order_message,
	"Payment Entry": _payment_message,
}


def _staff(user: str | None) -> str:
	if not user or user == "Administrator":
		return "Administrator"
	return get_fullname(user) or user


def _money(amount, currency) -> str:
	# The currency code rather than its symbol: "AED 1,234.50" stays readable in a
	# chat line, where a right-to-left symbol such as د.إ scrambles the layout.
	precision = cint(frappe.db.get_default("currency_precision")) or 2
	return f"{currency or ''} {fmt_money(flt(amount), precision=precision)}".strip()


def _qty(value) -> str:
	text = f"{flt(value):.3f}".rstrip("0").rstrip(".")
	return text or "0"


def _when(doc) -> str:
	return format_datetime(doc.modified or now_datetime(), "d MMM yyyy, HH:mm")


# ------------------------------------------------------------------- gateway


def _gateway(settings=None):
	settings = settings or get_settings()
	url = (settings.gateway_url or "").rstrip("/")
	if not url:
		raise GatewayError("WhatsApp Settings has no gateway URL.")
	key = settings.get_password("api_key", raise_exception=False) or ""
	return url, {"x-api-key": key, "content-type": "application/json"}


def gateway_request(method: str, path: str, payload: dict | None = None, settings=None) -> dict:
	url, headers = _gateway(settings)
	try:
		response = requests.request(method, url + path, json=payload, headers=headers, timeout=(5, 30))
	except requests.RequestException as exc:
		raise GatewayError(f"Could not reach the WhatsApp gateway at {url}: {exc}") from exc
	try:
		data = response.json()
	except ValueError:
		data = {}
	if response.status_code >= 400:
		raise GatewayError(data.get("error") or f"Gateway returned HTTP {response.status_code}")
	return data


def send_group_message(text: str, to: str | None = None) -> dict:
	"""Post one text message to the configured group. Runs as a background job;
	a failure raises so it lands in the Error Log and RQ Job list."""
	settings = get_settings()
	target = to or settings.group_id
	if not target:
		raise GatewayError("WhatsApp Settings has no group to post into.")
	return gateway_request("POST", "/send", {"to": target, "text": text}, settings)


# -------------------------------------------------------------------- health


def check_gateway_health():
	"""Scheduler, every minute: record the gateway's state on WhatsApp Settings."""
	settings = get_settings()
	if not settings.gateway_url:
		return
	try:
		data = gateway_request("GET", "/status", settings=settings)
	except GatewayError as exc:
		apply_health(settings, None, str(exc))
	else:
		apply_health(settings, data.get("state"), data.get("last_error") or "", data.get("number") or "")


def apply_health(settings, observed: str | None, error: str = "", number: str = "") -> str | None:
	"""Fold one observation into the settings. Writes only what changed, so a healthy
	link costs no database write per minute. Returns the new status when it changed."""
	previous = settings.status or ""
	failed = cint(settings.failed_checks)
	status = STATUS_BY_STATE.get(observed)
	if status:
		failed = 0
	else:
		failed = min(failed + 1, FAILED_CHECKS_FOR_DOWN)
		status = "Down" if failed >= FAILED_CHECKS_FOR_DOWN else (previous or "Connecting")
		if not error:
			error = f"gateway state: {observed}" if observed else "gateway not answering"
	if status == "Connected":
		error = ""

	updates = {
		"status": status,
		"failed_checks": failed,
		"last_error": (error or "")[:500],
		"linked_number": number if status == "Connected" else (settings.linked_number or ""),
	}
	changed = status != previous
	if changed:
		updates["status_changed_at"] = now_datetime()
	for field, value in updates.items():
		if (settings.get(field) or "") != (value or ""):
			frappe.db.set_single_value(SETTINGS, field, value)
	frappe.clear_document_cache(SETTINGS, SETTINGS)

	if changed and (status in ("Down", "Restricted") or previous == "Connected"):
		frappe.log_error(
			title=f"WhatsApp gateway: {status}",
			message=f"Status went from {previous or 'unknown'} to {status}.\n{error or ''}".strip(),
		)
	return status if changed else None


# ------------------------------------------------------------ desk helpers


def _require_manager():
	if not any(role in frappe.get_roles() for role in MANAGER_ROLES):
		frappe.throw("Not permitted", frappe.PermissionError)


def _or_throw(fn):
	try:
		return fn()
	except GatewayError as exc:
		frappe.throw(str(exc), title="WhatsApp gateway")


@frappe.whitelist()
def get_gateway_status() -> dict:
	_require_manager()
	return _or_throw(lambda: gateway_request("GET", "/status"))


@frappe.whitelist()
def get_groups() -> list[dict]:
	_require_manager()
	return _or_throw(lambda: gateway_request("GET", "/groups")).get("groups") or []


@frappe.whitelist()
def send_test_message() -> dict:
	_require_manager()
	settings = get_settings()
	if not settings.group_id:
		frappe.throw("Pick a group first.")
	text = (
		"*Sales App* test message\n"
		f"Sent by {_staff(frappe.session.user)} · {format_datetime(now_datetime(), 'd MMM yyyy, HH:mm')}"
	)
	return _or_throw(lambda: send_group_message(text))
