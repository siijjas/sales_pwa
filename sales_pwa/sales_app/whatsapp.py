"""WhatsApp notifications for the Sales App.

Orders and customer payments are announced in one WhatsApp group through the
Baileys gateway that ships in the app's whatsapp-gateway/ folder (a linked
device for the company's WhatsApp number, reached over a local HTTP API).

Flow: doc_events (hooks.py) call on_document_event() → the event is parked in
frappe.local until the transaction commits (so a save followed by a submit in the
same request posts once, and nothing is posted for a rolled-back change) → the
message is built from the committed document and sent from a background job, so
a slow or dead gateway never slows down or fails the sale itself.

Message text: each message is a Jinja template, editable on WhatsApp Settings
(order_template, payment_template) and falling back to DEFAULT_TEMPLATES when the
field is empty. Templates render in a sandbox with the variables listed in
TEMPLATE_HELP; a template that fails at send time is logged and the default is
used instead, so a typo never silences the group.

Adding a use case: write a `_<something>_context(doc, event, user)` builder, add a
default template, list both in MESSAGE_BUILDERS / DEFAULT_TEMPLATES, and hook the
doctype's events in hooks.py.

Health: check_gateway_health() runs every minute from the scheduler, asks the
gateway for its state and records it on WhatsApp Settings (status, linked
number, last error), raising one Error Log entry when the link goes down.
"""

import re

import requests
from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

import frappe
from frappe.utils import cint, cstr, escape_html, flt, fmt_money, format_datetime, get_fullname, now_datetime

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

DEFAULT_TEMPLATES = {
	"Sales Order": """*{{ heading }}*
Customer: {{ customer }}
{% if items %}
Items ({{ item_count }}):
{% for row in items %}
• {{ row.name }} × {{ row.qty }} {{ row.uom }}
{% endfor %}
{% if more %}
… and {{ more }} more
{% endif %}
{% else %}
Items: {{ item_count }} · {{ total_qty }} units
{% endif %}
{% if discount %}
Discount: {{ discount }}
{% endif %}
Total: {{ total }}
{% if event == "cancelled" %}
Status: Cancelled
{% elif doc.docstatus == 0 %}
Status: Draft, not yet confirmed
{% endif %}""",
	"Payment Entry": """*{{ heading }}*
Customer: {{ customer }}
Amount: {{ amount }} · {{ mode }}
{% if against %}
Against: {{ against }}
{% endif %}
{% if unallocated %}
Unallocated (advance): {{ unallocated }}
{% endif %}""",
}

# Shown on WhatsApp Settings next to the template fields.
TEMPLATE_HELP = {
	"Sales Order": [
		("heading", "🆕 New order, ✏️ Order updated, ✅ Order confirmed or ❌ Order cancelled"),
		("event", "created, updated, confirmed or cancelled"),
		("customer", "customer name"),
		("items", "the rows to list (empty when “List the order items” is off): row.name, row.qty, row.uom, row.amount"),
		("item_count", "number of rows on the order"),
		("more", "rows beyond “Items to list”"),
		("total_qty", "units on the order"),
		("discount", "discount with currency, empty when none"),
		("total", "grand total with currency"),
		("staff", "full name of the user who made the change"),
		("when", "date and time of the change"),
		("doc", "the Sales Order itself: doc.name, doc.delivery_date, doc.po_no, doc.customer_address …"),
	],
	"Payment Entry": [
		("heading", "💰 Payment received or ↩️ Payment cancelled"),
		("event", "received or cancelled"),
		("customer", "customer name"),
		("amount", "paid amount with currency"),
		("mode", "mode of payment"),
		("against", "“SAL-ORD-… (AED 400.00), …” for every allocated reference, empty when none"),
		("refs", "the allocated references: ref.name, ref.amount"),
		("unallocated", "advance with currency, empty when none"),
		("staff", "full name of the user who made the change"),
		("when", "date and time of the change"),
		("doc", "the Payment Entry itself: doc.name, doc.reference_no, doc.remarks …"),
	],
}

TEMPLATE_FIELDS = {"Sales Order": "order_template", "Payment Entry": "payment_template"}


def build_message(doc, event: str, user: str | None = None) -> str | None:
	builder = MESSAGE_BUILDERS.get(doc.doctype)
	if not builder:
		return None
	context = builder(doc, event, user)
	template = (get_settings().get(TEMPLATE_FIELDS[doc.doctype]) or "").strip()
	if template:
		try:
			return render_template(template, context)
		except TemplateError:
			frappe.log_error(
				title=f"WhatsApp template for {doc.doctype} failed, default used",
				message=frappe.get_traceback(),
			)
	return render_template(DEFAULT_TEMPLATES[doc.doctype], context)


_jenv = SandboxedEnvironment(autoescape=False)
# A template line holding nothing but {% %} tags: its line break is removed before
# rendering, so such a line never leaves a gap (Jinja's trim_blocks would also eat the
# break after an inline "{% if x %}text{% endif %}", gluing it to the next line).
_TAG_ONLY_LINE = re.compile(r"^[ \t]*((?:\{%(?:(?!%\}).)*%\}[ \t]*)+)\r?\n", re.MULTILINE)


def render_template(template: str, context: dict) -> str:
	"""Render a message template to plain text. Lines that only carry `{% %}` tags
	vanish, every other line is trimmed, blank lines are kept (one at most in a row,
	none at the ends), so a blank line in the template is a blank line in the message.
	Raises jinja2.TemplateError on a bad template."""
	source = _TAG_ONLY_LINE.sub(r"\1", template)
	text = _jenv.from_string(source).render(**context)
	lines = "\n".join(raw.strip() for raw in text.splitlines())
	return re.sub(r"\n{3,}", "\n\n", lines).strip()


def _order_context(doc, event: str, user: str | None) -> dict:
	settings = get_settings()
	rows = doc.get("items") or []
	limit = cint(settings.max_items) or len(rows)
	listed = rows[:limit] if settings.include_items else []
	return {
		"doc": doc,
		"event": event,
		"heading": ORDER_HEADINGS.get(event, event.title()),
		"customer": doc.customer_name or doc.customer,
		"items": [
			{
				"name": row.item_name or row.item_code,
				"code": row.item_code,
				"qty": _qty(row.qty),
				"uom": row.uom or "",
				"rate": _money(row.rate, doc.currency),
				"amount": _money(row.amount, doc.currency),
			}
			for row in listed
		],
		"item_count": len(rows),
		"more": max(len(rows) - len(listed), 0) if listed else 0,
		"total_qty": _qty(doc.total_qty),
		"discount": _money(doc.discount_amount, doc.currency) if flt(doc.discount_amount) else "",
		"total": _money(doc.grand_total, doc.currency),
		"staff": _staff(user or doc.owner),
		"when": _when(doc),
	}


def _payment_context(doc, event: str, user: str | None) -> dict:
	currency = doc.paid_from_account_currency or doc.paid_to_account_currency
	refs = [
		{"name": r.reference_name, "doctype": r.reference_doctype, "amount": _money(r.allocated_amount, currency)}
		for r in (doc.get("references") or [])
		if flt(r.allocated_amount)
	]
	return {
		"doc": doc,
		"event": event,
		"heading": PAYMENT_HEADINGS.get(event, event.title()),
		"customer": doc.party_name or doc.party,
		"amount": _money(doc.paid_amount, currency),
		"mode": doc.mode_of_payment or "No mode",
		"refs": refs,
		"against": ", ".join(f"{r['name']} ({r['amount']})" for r in refs),
		"unallocated": _money(doc.unallocated_amount, currency) if flt(doc.unallocated_amount) else "",
		"staff": _staff(user or doc.owner),
		"when": _when(doc),
	}


MESSAGE_BUILDERS = {
	"Sales Order": _order_context,
	"Payment Entry": _payment_context,
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


# ------------------------------------------------------- template samples


def sample_documents() -> dict:
	"""Unsaved documents used to validate and preview the templates."""
	so = frappe.new_doc("Sales Order")
	so.update(
		{
			"name": "SAL-ORD-2026-00012",
			"customer": "Al Noor Trading",
			"customer_name": "Al Noor Trading",
			"currency": "AED",
			"docstatus": 1,
			"total_qty": 40,
			"discount_amount": 15,
			"grand_total": 412.5,
			"modified": now_datetime(),
			"owner": frappe.session.user,
		}
	)
	for name, qty, uom, rate in (("Mineral Water 500ml", 24, "Nos", 1.5), ("Chips Salted", 10, "Pkt", 2), ("Juice Orange 1L", 6, "Nos", 6.25)):
		so.append("items", {"item_code": name, "item_name": name, "qty": qty, "uom": uom, "rate": rate, "amount": qty * rate})
	pe = frappe.new_doc("Payment Entry")
	pe.update(
		{
			"name": "ACC-PAY-2026-00031",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": "Al Noor Trading",
			"party_name": "Al Noor Trading",
			"mode_of_payment": "Cash",
			"paid_amount": 400,
			"paid_from_account_currency": "AED",
			"unallocated_amount": 0,
			"modified": now_datetime(),
			"owner": frappe.session.user,
		}
	)
	pe.append("references", {"reference_doctype": "Sales Order", "reference_name": "SAL-ORD-2026-00012", "allocated_amount": 400})
	return {"Sales Order": (so, "confirmed"), "Payment Entry": (pe, "received")}


def validate_templates(settings):
	"""Called from WhatsApp Settings.validate: a template that does not render
	against the sample documents is refused with Jinja's error."""
	samples = sample_documents()
	for doctype, field in TEMPLATE_FIELDS.items():
		template = (settings.get(field) or "").strip()
		if not template:
			continue
		doc, event = samples[doctype]
		try:
			render_template(template, MESSAGE_BUILDERS[doctype](doc, event, frappe.session.user))
		except TemplateError as exc:
			label = settings.meta.get_label(field)
			frappe.throw(f"{escape_html(label)}: {escape_html(str(exc))}", title="Template error")


@frappe.whitelist()
def preview_messages(order_template: str | None = None, payment_template: str | None = None) -> dict:
	"""What the two messages would look like for sample documents. Unsaved field
	values come from the form; empty means the built-in text."""
	_require_manager()
	given = {"Sales Order": order_template, "Payment Entry": payment_template}
	samples = sample_documents()
	out = {}
	for doctype, field in TEMPLATE_FIELDS.items():
		template = (given[doctype] or "").strip() or DEFAULT_TEMPLATES[doctype]
		doc, event = samples[doctype]
		try:
			out[field] = render_template(template, MESSAGE_BUILDERS[doctype](doc, event, frappe.session.user))
		except TemplateError as exc:
			out[field] = f"Template error: {exc}"
	return out


@frappe.whitelist()
def get_default_templates() -> dict:
	_require_manager()
	return {field: DEFAULT_TEMPLATES[doctype] for doctype, field in TEMPLATE_FIELDS.items()}


@frappe.whitelist()
def get_template_help() -> dict:
	_require_manager()
	return {field: TEMPLATE_HELP[doctype] for doctype, field in TEMPLATE_FIELDS.items()}


# ------------------------------------------------------------------- gateway


def _gateway(settings=None):
	settings = settings or get_settings()
	url = (settings.gateway_url or "").rstrip("/")
	if not url:
		raise GatewayError("WhatsApp Settings has no gateway URL.")
	key = settings.get_password("api_key", raise_exception=False) or ""
	return url, {"x-api-key": key, "content-type": "application/json"}


def gateway_request(method: str, path: str, payload: dict | None = None, settings=None) -> dict:
	"""One call to the gateway. Redirects are never followed: the API key travels in a
	header, and a redirect would carry it to whatever host the gateway URL pointed at."""
	url, headers = _gateway(settings)
	try:
		response = requests.request(
			method, url + path, json=payload, headers=headers, timeout=(5, 30), allow_redirects=False
		)
	except requests.RequestException as exc:
		raise GatewayError(f"Could not reach the WhatsApp gateway at {url}: {exc}") from exc
	try:
		data = response.json()
	except ValueError:
		data = {}
	if not isinstance(data, dict):
		data = {}
	if 300 <= response.status_code < 400:
		raise GatewayError(f"Gateway at {url} answered with a redirect (HTTP {response.status_code}), which is not followed.")
	if response.status_code >= 400:
		raise GatewayError(cstr(data.get("error") or "")[:300] or f"Gateway returned HTTP {response.status_code}")
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
		apply_health(settings, cstr(data.get("state") or ""), cstr(data.get("last_error") or ""), cstr(data.get("number") or ""))


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
		# msgprint renders HTML; the text may have come from the gateway, so escape it.
		frappe.throw(escape_html(str(exc)), title="WhatsApp gateway")


# What the desk gets to see of the gateway's answers: known keys only, coerced to plain
# types, so a gateway (or whatever the gateway URL points at) cannot hand the browser
# arbitrary structures, and a QR is only ever a PNG data URL.
_STATUS_STR = ("state", "number", "pairing_code", "last_error", "started_at", "connected_at", "last_sent_at")
_STATUS_INT = ("qr_age_seconds", "sent")


def _is_png_data_url(value) -> bool:
	return isinstance(value, str) and value.startswith("data:image/png;base64,") and len(value) < 200_000


def public_status(data: dict) -> dict:
	user = data.get("user") if isinstance(data.get("user"), dict) else None
	status = {
		"connected": bool(data.get("connected")),
		"qr_pending": bool(data.get("qr_pending")),
		"qr": data.get("qr") if _is_png_data_url(data.get("qr")) else None,
		"user": {"id": cstr(user.get("id") or "")[:100], "name": cstr(user.get("name") or "")[:100]} if user else None,
	}
	for key in _STATUS_STR:
		status[key] = cstr(data.get(key) or "")[:500] or None
	for key in _STATUS_INT:
		status[key] = cint(data.get(key))
	return status


def public_groups(data: dict) -> list[dict]:
	groups = data.get("groups")
	if not isinstance(groups, list):
		return []
	return [
		{
			"id": cstr(g.get("id"))[:100],
			"subject": cstr(g.get("subject") or "")[:200],
			"participants": cint(g.get("participants")),
		}
		for g in groups
		if isinstance(g, dict) and g.get("id")
	]


@frappe.whitelist()
def get_gateway_status() -> dict:
	_require_manager()
	return public_status(_or_throw(lambda: gateway_request("GET", "/status")))


@frappe.whitelist()
def get_groups() -> list[dict]:
	_require_manager()
	return public_groups(_or_throw(lambda: gateway_request("GET", "/groups")))


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
