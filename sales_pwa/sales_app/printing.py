"""Direct printing: a tap on Print puts paper in a printer on the shop's LAN.

The server is not on that LAN (it is a public host), and a browser cannot open a
socket to a printer, so the printer is reached the way cloud tills do it: a small
agent (print-agent/, Node, no dependencies) runs on any computer next to the
printers, polls this module over HTTPS with its token, and pushes what it gets to
the printers themselves. Nothing listens on the shop's network.

  Sales Print Agent   one per LAN; holds the token the agent polls with
  Sales Printer       a printer behind an agent: address, protocol, paper
  Sales Print Job     one document rendered for one printer: Queued → Sent → Printed / Failed
  Sales Profile       which printer each document goes to (blank = the PDF opens on the phone)

Two kinds of printer, two payloads, both rendered from the same print formats the
PDF download uses (pdf.py), so what prints is what the manager designed:

  Receipt (ESC/POS)   the format is rendered to a bitmap at the printer's dot pitch
                      (wkhtmltoimage) and sent as ESC/POS raster graphics, then cut.
                      Any format prints, in any script, on any ESC/POS printer such
                      as the Epson TM-T20. Pick a format designed for 80 mm paper.
  Document (PDF)      the PDF, handed to an office printer over IPP (what AirPrint
                      printers such as Brother lasers speak) or raw port 9100.

The agent's endpoints (agent_poll, agent_report) are guest-callable with the agent's
token in the X-Sales-Print-Token header and never expose anything but that agent's
own printers and jobs. A job the agent took but never answered is offered again
after SENT_TIMEOUT, up to MAX_ATTEMPTS. Old jobs go after KEEP_JOBS (daily task).
"""

from __future__ import annotations

import base64
import io
import secrets
import shutil
import subprocess
from datetime import timedelta

import frappe
from frappe.utils import cint, escape_html, get_datetime, now_datetime

from sales_pwa.sales_app.pdf import (
	PRINTABLE_DOCTYPES,
	SHIFT_DOCTYPES,
	_print_profile,
	allowed_print_formats,
	authorize_print,
	render_html,
	render_pdf,
	resolve_print_settings,
)
from sales_pwa.sales_app.utils import _is_manager, _manager_only

TOKEN_HEADER = "X-Sales-Print-Token"
RECEIPT = "Receipt (ESC/POS)"
DOCUMENT = "Document (PDF)"
PAYLOAD_OF = {RECEIPT: "escpos", DOCUMENT: "pdf"}
PROTOCOL_OF = {"Raw (port 9100)": "raw", "IPP": "ipp", "System printer": "system"}
MAX_SYSTEM_PRINTERS = 100

SENT_TIMEOUT = timedelta(minutes=2)
MAX_ATTEMPTS = 3
OFFLINE_AFTER = timedelta(minutes=3)
KEEP_JOBS = timedelta(days=7)
POLL_MS = 2000
JOBS_PER_POLL = 5

# Thermal printers print 8 dots per millimetre (203 dpi); the browser lays out CSS
# millimetres at 96 dpi. Rendering at this zoom makes a format designed in millimetres
# come out true to size on paper.
DOTS_PER_MM = 8
CSS_PX_PER_MM = 96 / 25.4
PRINTABLE_MM = {"80": 72, "58": 48}
# Anything lighter than this prints white; text stays crisp instead of dithered.
INK_THRESHOLD = 180
MAX_RECEIPT_ROWS = 24000  # 3 m of paper: a runaway format must not empty the roll

PRINTER_FIELD_OF = {
	"Sales Order": "order_printer",
	"Sales Invoice": "invoice_printer",
	"Payment Entry": "payment_printer",
	"Sales Shift Opening": "shift_report_printer",
	"Sales Shift Closing": "shift_report_printer",
}

ESC, GS = b"\x1b", b"\x1d"


# ---------------------------------------------------------------------------
# Which printer
# ---------------------------------------------------------------------------
def _printer(name: str | None):
	"""The printer row with its agent's state, or None when it cannot print now."""
	if not name:
		return None
	row = frappe.db.get_value(
		"Sales Printer",
		name,
		["name", "printer_type", "is_active", "agent", "host", "port", "protocol", "ipp_path", "system_printer", "paper_width", "scale", "cut_paper", "open_drawer", "last_contact_at", "last_status"],
		as_dict=True,
	)
	if not row or not row.is_active:
		return None
	agent = frappe.db.get_value("Sales Print Agent", row.agent, ["is_active", "last_contact_at"], as_dict=True)
	if not agent or not agent.is_active:
		return None
	row.agent_last_contact_at = agent.last_contact_at
	return row


def resolve_printer(doc):
	"""The Sales Printer this document goes to for the caller, or None for the PDF.

	A credit note takes the credit-note printer, then the invoice one. Managers
	without a profile print the way the document's owner would (pdf._print_profile).
	"""
	profile = _print_profile(doc)
	if not profile:
		return None
	fields = []
	if doc.doctype == "Sales Invoice" and doc.get("is_return"):
		fields.append("return_printer")
	field = PRINTER_FIELD_OF.get(doc.doctype)
	if field:
		fields.append(field)
	for name in fields:
		printer = _printer(profile.get(name))
		if printer:
			return printer
	return None


def _online(last_contact_at, now=None) -> bool:
	if not last_contact_at:
		return False
	return (now or now_datetime()) - get_datetime(last_contact_at) <= OFFLINE_AFTER


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def receipt_css(width_css_px: int) -> str:
	"""Pin the page to the paper: wkhtmltoimage's smart width would otherwise grow the
	image to fit the widest table (an A4 format then comes out as a 36000-dot line of
	nothing), and the print view's own toolbar and gutter must not reach the paper."""
	return f"""
<style id="sales-pwa-receipt">
html, body {{ margin: 0 !important; padding: 0 !important; background: #fff !important; width: {width_css_px}px !important; min-width: 0 !important; max-width: {width_css_px}px !important; overflow-x: hidden !important; }}
.print-format-gutter {{ padding: 0 !important; margin: 0 !important; background: #fff !important; width: {width_css_px}px !important; overflow: hidden !important; }}
.print-format {{ width: {width_css_px}px !important; max-width: {width_css_px}px !important; min-height: 0 !important; margin: 0 !important; padding: 1mm !important; box-sizing: border-box !important; box-shadow: none !important; border: 0 !important; background: #fff !important; overflow: hidden !important; }}
.print-format * {{ color: #000 !important; -webkit-print-color-adjust: exact; }}
.print-format table {{ table-layout: fixed !important; width: 100% !important; max-width: 100% !important; word-wrap: break-word; }}
.print-format img {{ max-width: 100% !important; height: auto; }}
.print-hide, .hidden-print, .action-banner, .print-toolbar {{ display: none !important; }}
</style>
"""


def _wkhtmltoimage() -> str:
	path = shutil.which("wkhtmltoimage")
	if not path:
		frappe.throw(frappe._("wkhtmltoimage is not installed on the server; receipt printing needs it."))
	return path


def html_to_png(html: str, width_dots: int, zoom: float) -> bytes:
	"""Render HTML to a PNG `width_dots` wide, laid out at `zoom` device pixels per CSS pixel."""
	css = receipt_css(round(width_dots / zoom))
	# Last in the document, so it outranks every stylesheet the print view carries.
	if "</body>" in html:
		html = html.replace("</body>", css + "</body>", 1)
	else:
		html += css
	args = [
		_wkhtmltoimage(),
		"--quiet",
		"--encoding", "utf-8",
		"--format", "png",
		"--width", str(width_dots),
		"--zoom", f"{zoom:.4f}",
		"--disable-javascript",
		"--load-error-handling", "ignore",
		"--load-media-error-handling", "ignore",
		"-", "-",
	]
	try:
		result = subprocess.run(args, input=html.encode("utf-8"), capture_output=True, timeout=60, check=False)
	except subprocess.TimeoutExpired:
		frappe.throw(frappe._("Rendering the receipt took too long."))
	if result.returncode != 0 and not result.stdout:
		frappe.log_error(title="Receipt rendering failed", message=result.stderr.decode("utf-8", "replace")[-2000:])
		frappe.throw(frappe._("The receipt could not be rendered. See the Error Log."))
	return result.stdout


def png_to_raster(png: bytes, width_dots: int) -> tuple[bytes, int]:
	"""(packed 1-bit rows, row count) of the image, 1 = ink, trimmed of blank paper below."""
	from PIL import Image, ImageOps

	image = Image.open(io.BytesIO(png))
	if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
		background = Image.new("RGBA", image.size, (255, 255, 255, 255))
		background.alpha_composite(image.convert("RGBA"))
		image = background
	gray = image.convert("L")
	if gray.width != width_dots:
		# Smart width can make the page wider than asked when something overflows.
		gray = gray.resize((width_dots, max(1, round(gray.height * width_dots / gray.width))), Image.LANCZOS)
	ink = ImageOps.invert(gray).point(lambda v: 255 if v >= 255 - INK_THRESHOLD else 0)
	box = ink.getbbox()
	bottom = box[3] if box else 1
	ink = ink.crop((0, 0, width_dots, bottom))
	if ink.height > MAX_RECEIPT_ROWS:
		frappe.throw(frappe._("The receipt is longer than {0} cm; pick a format designed for receipt paper.").format(MAX_RECEIPT_ROWS // DOTS_PER_MM // 10))
	bits = ink.convert("1", dither=Image.NONE)
	return bits.tobytes(), bits.height


def escpos_receipt(raster: bytes, rows: int, width_dots: int, *, cut: bool = True, drawer: bool = False, band_rows: int = 512) -> bytes:
	"""Initialise, the bitmap as GS v 0 bands, feed, cut, and the drawer pulse."""
	stride = (width_dots + 7) // 8
	out = bytearray(ESC + b"@" + ESC + b"a\x00")
	for top in range(0, rows, band_rows):
		height = min(band_rows, rows - top)
		out += GS + b"v0\x00" + bytes([stride & 0xFF, stride >> 8, height & 0xFF, height >> 8])
		out += raster[top * stride : (top + height) * stride]
	out += ESC + b"d\x03"
	if cut:
		out += GS + b"V\x42\x00"
	if drawer:
		out += ESC + b"p\x00\x19\xfa"
	return bytes(out)


def render_receipt(html: str, printer) -> bytes:
	printable_mm = PRINTABLE_MM.get(str(printer.paper_width), PRINTABLE_MM["80"])
	width_dots = printable_mm * DOTS_PER_MM
	zoom = (DOTS_PER_MM / CSS_PX_PER_MM) * (cint(printer.scale) or 100) / 100
	raster, rows = png_to_raster(html_to_png(html, width_dots, zoom), width_dots)
	return escpos_receipt(raster, rows, width_dots, cut=bool(printer.cut_paper), drawer=bool(printer.open_drawer))


def render_for(printer, html: str) -> tuple[str, bytes]:
	"""(payload type, bytes) of `html` for this printer."""
	if printer.printer_type == RECEIPT:
		return "escpos", render_receipt(html, printer)
	return "pdf", render_pdf(html)


# ---------------------------------------------------------------------------
# The queue
# ---------------------------------------------------------------------------
def enqueue(printer: str, payload_type: str, data: bytes, *, label: str = "", ref_doctype: str | None = None, ref_name: str | None = None, print_format: str | None = None) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Sales Print Job",
			"printer": printer,
			"status": "Queued",
			"label": (label or "")[:140],
			"ref_doctype": ref_doctype,
			"ref_name": ref_name,
			"print_format": print_format,
			"requested_by": frappe.session.user,
			"payload_type": payload_type,
			"attempts": 0,
			"content": base64.b64encode(data).decode("ascii"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _requeue_stale(printer_names: list[str], now) -> None:
	"""Handed over, never answered: offer again, or give up after MAX_ATTEMPTS."""
	if not printer_names:
		return
	stale = frappe.get_all(
		"Sales Print Job",
		filters={"printer": ("in", printer_names), "status": "Sent", "sent_at": ("<", now - SENT_TIMEOUT)},
		fields=["name", "attempts"],
	)
	for job in stale:
		if cint(job.attempts) >= MAX_ATTEMPTS:
			frappe.db.set_value("Sales Print Job", job.name, {"status": "Failed", "error": "No answer from the print agent.", "done_at": now}, update_modified=False)
		else:
			frappe.db.set_value("Sales Print Job", job.name, "status", "Queued", update_modified=False)


def collect(printer_names: list[str], *, limit: int = JOBS_PER_POLL, now=None) -> list:
	"""Queued jobs of these printers, oldest first, marked Sent: what one poll hands over."""
	now = now or now_datetime()
	_requeue_stale(printer_names, now)
	if not printer_names:
		return []
	names = frappe.db.sql(
		"select name from `tabSales Print Job` where printer in %(printers)s and status = 'Queued' order by creation asc, name asc limit %(limit)s for update",
		{"printers": tuple(printer_names), "limit": limit},
		pluck=True,
	)
	jobs = []
	for name in names:
		frappe.db.sql(
			"update `tabSales Print Job` set status = 'Sent', sent_at = %s, attempts = coalesce(attempts, 0) + 1 where name = %s",
			(now, name),
		)
		jobs.append(frappe.db.get_value("Sales Print Job", name, ["name", "printer", "label", "payload_type", "content"], as_dict=True))
	return jobs


def finish(job: str, *, ok: bool, error: str = "", printer_names: list[str] | None = None, now=None) -> dict | None:
	"""Record the agent's answer. Only a job of one of `printer_names` (the agent's own) is touched."""
	row = frappe.db.get_value("Sales Print Job", job, ["name", "printer", "label", "status"], as_dict=True)
	if not row or (printer_names is not None and row.printer not in printer_names):
		return None
	now = now or now_datetime()
	frappe.db.set_value(
		"Sales Print Job",
		job,
		{"status": "Printed" if ok else "Failed", "error": "" if ok else (error or "The printer reported an error.")[:500], "done_at": now},
		update_modified=False,
	)
	printer_seen(row.printer, f"Printed {row.label}" if ok else f"Failed: {error or 'printer error'}", now=now)
	return row


def retry(job: str) -> None:
	frappe.db.set_value("Sales Print Job", job, {"status": "Queued", "attempts": 0, "error": "", "done_at": None, "sent_at": None}, update_modified=False)


def printer_seen(printer: str, status: str, *, now=None) -> None:
	frappe.db.set_value("Sales Printer", printer, {"last_contact_at": now or now_datetime(), "last_status": (status or "")[:140]}, update_modified=False)


def purge_old_jobs() -> int:
	"""Daily: jobs older than KEEP_JOBS go, content and all."""
	cutoff = now_datetime() - KEEP_JOBS
	names = frappe.get_all("Sales Print Job", filters={"creation": ("<", cutoff)}, pluck="name")
	for start in range(0, len(names), 500):
		frappe.db.delete("Sales Print Job", {"name": ("in", names[start : start + 500])})
	return len(names)


# ---------------------------------------------------------------------------
# Staff screens
# ---------------------------------------------------------------------------
def _job_label(doc) -> str:
	if doc.doctype == "Sales Invoice" and doc.get("is_return"):
		return f"Credit note {doc.name}"
	if doc.doctype == "Payment Entry":
		return f"Payment {doc.name}"
	if doc.doctype in SHIFT_DOCTYPES:
		return f"Shift report {doc.name}"
	return f"{doc.doctype} {doc.name}"


def _job_payload(job_name: str, printer) -> dict:
	return {
		"job": job_name,
		"printer": printer.name,
		"printer_type": printer.printer_type,
		"online": _online(printer.agent_last_contact_at),
	}


def _chosen_printer(name: str):
	"""An active printer the caller picked by name (the app's print setup), or a refusal."""
	printer = _printer(name)
	if not printer:
		frappe.throw(frappe._("Printer {0} is not available: it or its print agent is switched off.").format(name))
	return printer


@frappe.whitelist()
def print_choices(doctype: str):
	"""What the print sheet offers for a doctype: the enabled formats the caller's
	profile allows (pdf.allowed_print_formats) and the printers that can print now, plus what the profile would pick for this person
	when they choose nothing (the "profile default" the sheet marks).
	"""
	if doctype not in PRINTABLE_DOCTYPES:
		frappe.throw(frappe._("The app does not print {0} documents.").format(doctype), frappe.PermissionError)
	probe = frappe._dict(doctype=doctype, is_return=0, owner=None)
	default_format, _letter_head = resolve_print_settings(probe)
	default_printer = resolve_printer(probe)
	allowed = allowed_print_formats(doctype)
	if allowed is None:
		formats = [{"name": "Standard"}] + frappe.get_all(
			"Print Format", filters={"doc_type": doctype, "disabled": 0}, fields=["name"], order_by="name asc", limit_page_length=200
		)
		default_format = default_format or "Standard"
	else:
		# The profile limits this doctype to the formats it lists (pdf.allowed_print_formats).
		formats = [{"name": name} for name in allowed]
		if default_format not in allowed:
			default_format = allowed[0] if allowed else None
	now = now_datetime()
	agents = {a.name: a for a in frappe.get_all("Sales Print Agent", filters={"is_active": 1}, fields=["name", "last_contact_at"])}
	printers = []
	for printer in frappe.get_all("Sales Printer", filters={"is_active": 1}, fields=["name", "printer_type", "agent"], order_by="name asc"):
		agent = agents.get(printer.agent)
		if not agent:
			continue
		printers.append({"name": printer.name, "printer_type": printer.printer_type, "online": _online(agent.last_contact_at, now)})
	return {
		"doctype": doctype,
		"formats": formats,
		"default_format": default_format,
		"printers": printers,
		"default_printer": default_printer.name if default_printer else None,
	}


@frappe.whitelist(methods=["POST"])
def print_document(doctype: str, name: str, format: str | None = None, printer: str | None = None):
	"""Queue `name` for a printer: the one the caller names (their print setup in the
	app), else the one their profile names for this doctype.

	Returns {"job": None} when no printer applies: the app then opens the PDF, as
	before. Same authorization as the PDF download (pdf.authorize_print). The
	document is rendered now, so a broken format fails here, in front of the person.
	"""
	doc = authorize_print(doctype, name, format)
	printer = _chosen_printer(printer) if printer else resolve_printer(doc)
	if not printer:
		return {"job": None}
	html, used_format = render_html(doc, format)
	payload_type, data = render_for(printer, html)
	job = enqueue(printer.name, payload_type, data, label=_job_label(doc), ref_doctype=doctype, ref_name=name, print_format=used_format)
	return _job_payload(job, printer)


@frappe.whitelist()
def job_status(job: str):
	"""Where a job the caller sent stands (managers may ask about any job)."""
	row = frappe.db.get_value("Sales Print Job", job, ["name", "status", "error", "requested_by", "printer", "attempts"], as_dict=True)
	if not row or (row.requested_by != frappe.session.user and not _is_manager()):
		frappe.throw(frappe._("No such print job."), frappe.DoesNotExistError)
	return {"job": row.name, "status": row.status, "error": row.error or "", "printer": row.printer, "attempts": cint(row.attempts)}


@frappe.whitelist()
def printer_status():
	"""Every active printer with whether its agent is online: the Staff screen's printer strip."""
	_manager_only()
	now = now_datetime()
	agents = {a.name: a for a in frappe.get_all("Sales Print Agent", fields=["name", "is_active", "last_contact_at", "last_status", "agent_host"])}
	rows = []
	for printer in frappe.get_all(
		"Sales Printer",
		filters={"is_active": 1},
		fields=["name", "printer_type", "agent", "host", "port", "protocol", "system_printer", "paper_width", "last_contact_at", "last_status"],
		order_by="name asc",
	):
		agent = agents.get(printer.agent)
		waiting = frappe.db.count("Sales Print Job", {"printer": printer.name, "status": ("in", ["Queued", "Sent"])})
		failed = frappe.db.count("Sales Print Job", {"printer": printer.name, "status": "Failed", "creation": (">=", now - timedelta(days=1))})
		rows.append(
			{
				"name": printer.name,
				"printer_type": printer.printer_type,
				"host": printer.host,
				"port": printer.port,
				"protocol": printer.protocol,
				"system_printer": printer.system_printer or "",
				"paper_width": printer.paper_width,
				"agent": printer.agent,
				"agent_active": bool(agent and agent.is_active),
				"agent_online": bool(agent and agent.is_active and _online(agent.last_contact_at, now)),
				"agent_host": (agent and agent.agent_host) or "",
				"last_status": printer.last_status or "",
				"last_contact_at": str(printer.last_contact_at) if printer.last_contact_at else None,
				"waiting": waiting,
				"failed_today": failed,
			}
		)
	return rows


def _test_html(printer) -> str:
	who = escape_html(frappe.utils.get_fullname(frappe.session.user))
	when = escape_html(frappe.utils.format_datetime(now_datetime()))
	site = escape_html(frappe.local.site)
	return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ font-family: Arial, Helvetica, sans-serif; color: #000; }}
.print-format {{ font-size: 12px; }}
h1 {{ font-size: 18px; margin: 0 0 4px; text-align: center; }}
p {{ margin: 2px 0; }} .rule {{ border-top: 1px dashed #000; margin: 6px 0; }}
.big {{ font-size: 16px; font-weight: bold; text-align: center; }}
</style></head><body><div class="print-format-gutter"><div class="print-format">
<h1>Sales App</h1>
<p class="big">Test page</p>
<div class="rule"></div>
<p>Printer: {escape_html(printer.name)}</p>
<p>Type: {escape_html(printer.printer_type)}</p>
<p>Address: {escape_html(printer.system_printer if printer.protocol == "System printer" else f"{printer.host}:{printer.port}")}</p>
<p>Agent: {escape_html(printer.agent)}</p>
<p>Site: {site}</p>
<p>Requested by {who} on {when}</p>
<div class="rule"></div>
<p>If you can read this, the agent reaches both the server and the printer.</p>
<p style="text-align:center">0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ</p>
</div></div></body></html>"""


def test_print(printer_name: str) -> dict:
	"""A test page on this printer, for managers. Used by the doctype button and the app."""
	_manager_only()
	printer = _printer(printer_name)
	if not printer:
		frappe.throw(frappe._("Printer {0} is not active, or its agent is not.").format(printer_name))
	payload_type, data = render_for(printer, _test_html(printer))
	job = enqueue(printer.name, payload_type, data, label="Test page")
	return _job_payload(job, printer)


@frappe.whitelist(methods=["POST"])
def test_printer(printer: str):
	return test_print(printer)


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------
def _token_from_request() -> str:
	request = getattr(frappe.local, "request", None)
	token = ""
	if request is not None:
		token = request.headers.get(TOKEN_HEADER) or ""
		if not token:
			auth = request.headers.get("Authorization") or ""
			if auth.lower().startswith("bearer "):
				token = auth[7:].strip()
	return token or str(frappe.form_dict.get("token") or "")


def _agent_from_token():
	"""The active agent whose token the request carries, compared in constant time."""
	given = _token_from_request()
	if not given:
		frappe.throw(frappe._("Missing agent token."), frappe.AuthenticationError)
	for agent in frappe.get_all("Sales Print Agent", filters={"is_active": 1}, fields=["name", "token"]):
		if agent.token and secrets.compare_digest(str(agent.token), given):
			return agent
	frappe.throw(frappe._("Unknown agent token."), frappe.AuthenticationError)


def _agent_printers(agent_name: str) -> list:
	return frappe.get_all(
		"Sales Printer",
		filters={"agent": agent_name, "is_active": 1},
		fields=["name", "printer_type", "host", "port", "protocol", "ipp_path", "system_printer"],
		order_by="name asc",
	)


def _printer_payload(printer) -> dict:
	return {
		"id": printer.name,
		"name": printer.name,
		"type": PAYLOAD_OF.get(printer.printer_type, "escpos"),
		"host": printer.host,
		"port": cint(printer.port) or (631 if printer.protocol == "IPP" else 9100),
		"protocol": PROTOCOL_OF.get(printer.protocol, "raw"),
		"ipp_path": printer.ipp_path or "/ipp/print",
		"system_printer": printer.system_printer or "",
	}


def _record_agent(agent, now) -> None:
	values = {"last_contact_at": now, "last_status": "Polling"}
	version = str(frappe.form_dict.get("version") or "")[:40]
	host = str(frappe.form_dict.get("host") or "")[:140]
	if version:
		values["agent_version"] = version
	if host:
		values["agent_host"] = host
	# The printers installed on the agent's computer, for the System printer picker.
	system = frappe.form_dict.get("system_printers")
	if isinstance(system, str) and system:
		system = frappe.parse_json(system)
	if isinstance(system, list):
		names = [str(n)[:140] for n in system if isinstance(n, (str, int, float)) and str(n).strip()]
		values["system_printers"] = frappe.as_json(names[:MAX_SYSTEM_PRINTERS])
	frappe.db.set_value("Sales Print Agent", agent.name, values, update_modified=False)


def _record_printer_checks(printer_names: list[str], now) -> None:
	"""The agent's reachability checks: {printer id: {"ok": bool, "message": str}}."""
	checks = frappe.form_dict.get("printers")
	if isinstance(checks, str):
		checks = frappe.parse_json(checks) if checks else None
	if not isinstance(checks, dict):
		return
	for name, check in checks.items():
		if name not in printer_names or not isinstance(check, dict):
			continue
		ok = check.get("ok") in (True, 1, "1", "true")
		message = str(check.get("message") or "")[:120]
		printer_seen(name, ("Reachable" if ok else f"Unreachable: {message or 'no answer'}"), now=now)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def agent_poll():
	"""The agent asks for work: its printers, and up to JOBS_PER_POLL queued jobs, now Sent."""
	agent = _agent_from_token()
	now = now_datetime()
	printers = _agent_printers(agent.name)
	names = [p.name for p in printers]
	_record_agent(agent, now)
	_record_printer_checks(names, now)
	jobs = collect(names, now=now)
	return {
		"agent": agent.name,
		"poll_ms": POLL_MS,
		"printers": [_printer_payload(p) for p in printers],
		"jobs": [
			{"id": j.name, "printer": j.printer, "label": j.label or "", "payload": j.payload_type, "data": j.content}
			for j in jobs
		],
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def agent_report(job: str, ok=True, error: str = ""):
	"""The agent says how a job went."""
	agent = _agent_from_token()
	names = [p.name for p in _agent_printers(agent.name)]
	done = finish(str(job), ok=ok in (True, 1, "1", "true"), error=str(error or ""), printer_names=names)
	frappe.db.set_value("Sales Print Agent", agent.name, {"last_contact_at": now_datetime(), "last_status": "Printed" if done and ok in (True, 1, "1", "true") else "Reported an error"}, update_modified=False)
	return {"ok": bool(done)}
