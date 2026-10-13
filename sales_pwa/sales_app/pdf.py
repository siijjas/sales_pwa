"""PDF download for the PWA.

Frappe's own ``download_pdf`` leaves the print stylesheet as a ``<link>`` that
wkhtmltopdf then fetches from the site's public URL. On servers that sit behind a
proxy / CDN that fetch can come back 404 (a cached miss, a hostname that resolves to
another vhost, a stale asset hash) and wkhtmltopdf aborts the whole PDF with
``ContentNotFoundError`` even though the HTML itself rendered fine. A missing image
only drops the image, but a missing stylesheet kills the PDF.

So this endpoint renders the same HTML, inlines the print stylesheet from disk, and
tells wkhtmltopdf to ignore media it cannot load. The PDF then never depends on the
server being able to reach itself over the network.
"""

import os
import re
from contextlib import contextmanager

import frappe
from frappe.utils import cint
from frappe.utils.pdf import get_pdf
from frappe.www.printview import validate_print_permission

from sales_pwa.sales_app.utils import _get_driver_config, _is_manager, _validate_customer_access

SHIFT_DOCTYPES = ("Sales Shift Opening", "Sales Shift Closing")
# Customer documents the app prints; a staff member may print those of customers they serve.
CUSTOMER_DOCTYPES = ("Sales Order", "Sales Invoice", "Payment Entry")


@contextmanager
def _render_with_full_read():
	"""Render a print format with Administrator's read rights.

	Print formats are manager-authored templates, and some query doctypes the staff
	role cannot read (ERPNext's payment voucher lists the GL Entry rows), which
	fails the whole print with a PrintFormatError. The caller has already been
	authorized for this document and the format has been checked against its
	doctype, so the template itself renders unrestricted. Only the session's user is
	swapped for the render; the session record and sid are untouched.
	"""
	session = frappe.local.session
	user = session.user
	session.user = "Administrator"
	frappe.local.role_permissions = {}
	try:
		yield
	finally:
		session.user = user
		frappe.local.role_permissions = {}

_STYLESHEET_LINK = re.compile(r'<link[^>]+href="(?P<href>[^"]*/assets/[^"]+\.css)"[^>]*>', re.IGNORECASE)


def _inline_stylesheets(html: str) -> str:
	"""Replace ``<link href="/assets/....css">`` tags with the file's contents."""

	def replace(match: re.Match) -> str:
		href = match.group("href").split("?", 1)[0]
		rel = href.split("/assets/", 1)[1]
		path = os.path.join(frappe.local.sites_path, "assets", rel)
		if not os.path.isfile(path):
			return match.group(0)
		with open(path, encoding="utf-8") as f:
			css = f.read()
		# Relative url(...) references (fonts) would otherwise resolve against the page.
		base = "/assets/" + rel.rsplit("/", 1)[0] + "/"
		css = re.sub(r"url\((['\"]?)(?!data:|https?:|/)", lambda m: f"url({m.group(1)}{base}", css)
		return f"<style>{css}</style>"

	return _STYLESHEET_LINK.sub(replace, html)


def _print_profile(doc) -> dict | None:
	"""The Sales Profile whose print settings apply to this print.

	The caller's own profile when they have one. A manager without a profile prints
	the way the staff member who raised the document would, so the back office gets
	the same paper the customer got.
	"""
	config = _get_driver_config(required=False)
	if config or not doc.get("owner"):
		return config
	from sales_pwa.sales_app.van_profile import get_van_profile_for_driver

	return get_van_profile_for_driver(doc.owner)


def _usable_print_format(name: str | None, doctype: str) -> str | None:
	"""`name` if it is an enabled print format for `doctype`; a stale setting prints Standard."""
	if not name:
		return None
	row = frappe.db.get_value("Print Format", name, ["doc_type", "disabled"], as_dict=True)
	if not row or row.doc_type != doctype or row.disabled:
		return None
	return name


def resolve_print_settings(doc) -> tuple[str | None, str | None]:
	"""(print format, letter head) the Sales Profile asks for on this document.

	Either is None when the profile leaves it blank, so Frappe falls back to the
	doctype's default format and the company's default letter head. A credit note
	(Sales Invoice with is_return) takes the return format first, then the invoice one.
	"""
	profile = _print_profile(doc)
	if not profile:
		return None, None
	fields = []
	if doc.doctype == "Sales Invoice":
		if doc.get("is_return"):
			fields.append("return_print_format")
		fields.append("invoice_print_format")
	elif doc.doctype == "Sales Order":
		fields.append("order_print_format")
	elif doc.doctype == "Payment Entry":
		fields.append("payment_print_format")
	print_format = None
	for field in fields:
		print_format = _usable_print_format(profile.get(field), doc.doctype)
		if print_format:
			break
	letter_head = profile.get("letter_head") or None
	if letter_head and not frappe.db.exists("Letter Head", {"name": letter_head, "disabled": 0}):
		letter_head = None
	return print_format, letter_head


@frappe.whitelist()
def download_pdf(doctype: str, name: str, format: str | None = None, no_letterhead: int = 0):
	"""Drop-in for ``frappe.utils.print_format.download_pdf`` (same query parameters).

	With no ``format`` the Sales Profile decides (see resolve_print_settings); the
	shift reports name their own formats explicitly.
	"""
	doc = frappe.get_doc(doctype, name)
	validate_print_permission(doc)
	# Drivers hold a plain read/print DocPerm on shift documents; the app limits them
	# to their own shifts (managers see everyone's), same as the report endpoints.
	if doctype in SHIFT_DOCTYPES and not _is_manager() and doc.driver != frappe.session.user:
		frappe.throw(frappe._("You can only print your own shift reports."), frappe.PermissionError)
	if doctype in CUSTOMER_DOCTYPES and not _is_manager():
		if doctype == "Payment Entry" and doc.party_type != "Customer":
			frappe.throw(frappe._("You can only print customer payments."), frappe.PermissionError)
		_validate_customer_access(doc.party if doctype == "Payment Entry" else doc.customer)
	# The render below runs unrestricted, so a format must belong to this doctype.
	if format and format != "Standard" and frappe.db.get_value("Print Format", format, "doc_type") != doctype:
		frappe.throw(frappe._("{0} is not a {1} print format.").format(format, doctype))

	letterhead = None
	if not format:
		format, letterhead = resolve_print_settings(doc)

	with _render_with_full_read():
		html = frappe.get_print(
			doctype, name, format, doc=doc, no_letterhead=cint(no_letterhead), letterhead=letterhead
		)
	html = _inline_stylesheets(html)
	pdf = get_pdf(html, options={"load-media-error-handling": "ignore"})

	frappe.local.response.filename = "{}.pdf".format(name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"
