# Print agent

Direct printing from the Sales App to printers on the shop's LAN: an Epson TM-T20
(or any ESC/POS receipt printer) and an office printer such as a Brother laser.

The Sales App server is on the internet and cannot see the shop's printers, and a
phone's browser cannot talk to a printer either. So a small agent runs on any
computer on the same LAN as the printers. It only makes outbound HTTPS requests to
the site (nothing listens, no port forwarding, no VPN): it asks for print jobs,
pushes them to the printers, and reports back. The server renders every job from
the same print formats the PDF download uses.

| Printer | Set up as | What the agent sends |
| --- | --- | --- |
| Epson TM-T20 (receipt) | **Receipt (ESC/POS)**, Raw, port 9100 | The print format rendered as a bitmap at 203 dpi, as ESC/POS raster graphics, then a cut |
| Brother (office) | **Document (PDF)**, IPP, port 631, path `/ipp/print` | The PDF, as an IPP Print-Job (what AirPrint uses) |
| Any printer installed on the agent's computer | either type, **System printer** | Receipts as raw bytes to the Windows queue (or `lp -o raw`); PDFs through SumatraPDF on Windows, `lp` elsewhere |

Any ESC/POS printer with an Ethernet or Wi-Fi port takes the receipt path. Any
AirPrint-capable printer takes the PDF path; most Brother, HP, Canon and Epson
office printers since 2012 are. A printer that prints PDF files natively over port
9100 can also be set to Raw.

**System printer** is for everything else: a USB printer, a printer that only works
through its Windows driver (a GDI or "host-based" Brother that refuses PDF over
IPP), or simply a printer you would rather manage in Windows than by IP address.
The agent then goes through the operating system's print spooler, so the printer
must be installed on the computer the agent runs on. On Windows, printing PDFs this
way needs [SumatraPDF](https://www.sumatrapdfreader.org) (free, one file): put
`SumatraPDF.exe` next to `agent.mjs`, or install it, or point `SP_SUMATRA` at it.
Receipts need nothing extra. On Linux and macOS, CUPS (`lp`) handles both.

## 1. Create the agent in the desk

In the desk, **Sales Print Agent → New**: give it a name (say *Shop PC*) and save.
A token appears on the form. Keep it private: it is the only thing the agent
authenticates with. *Regenerate token* invalidates the old one.

## 2. Run the agent on a computer next to the printers

Needs [Node.js](https://nodejs.org) 20 or newer. Copy this folder (`print-agent/`)
to that computer, then:

```bash
cd print-agent
cp .env.example .env        # set SP_SERVER_URL and SP_AGENT_TOKEN
npm start
```

There is nothing to install: the agent has no dependencies. On start it logs
`connected; serving N printer(s)` and the agent's form in the desk shows *Online*.

Give each printer a fixed IP address (or a DHCP reservation on the router) so the
address you enter next does not change.

### Keep it running

**Windows:** the simplest is a scheduled task that runs at logon or at startup:
Task Scheduler → Create Task → trigger *At startup* → action
`"C:\Program Files\nodejs\node.exe"` with argument `agent.mjs` and *Start in* set to
the `print-agent` folder; tick *Run whether user is logged on or not*. Or install it
as a service with [NSSM](https://nssm.cc) (`nssm install SalesPrintAgent`).

**Linux / Raspberry Pi (systemd, no root needed):**

```bash
mkdir -p ~/.config/systemd/user
cp deploy/sales-pwa-print-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sales-pwa-print-agent
journalctl --user -u sales-pwa-print-agent -f
loginctl enable-linger $USER   # once, so it runs while nobody is logged in
```

Edit the paths in the unit if the folder is not `~/print-agent`.

**macOS:** a `launchd` user agent, or just leave it running in a Terminal window.

## 3. Add the printers in the desk

**Sales Printer → New**, one per printer, with the agent you just created:

- **Epson TM-T20:** type *Receipt (ESC/POS)*, protocol *Raw (port 9100)*, the
  printer's IP, paper width 80 (or 58). *Cut after printing* is on; tick *Open the
  cash drawer* if a drawer is plugged into the printer. *Scale* is 100 for a format
  designed in millimetres; lower it to fit a wider format, raise it for bigger text.
- **Brother:** type *Document (PDF)*, protocol *IPP*, the printer's IP, port 631,
  path `/ipp/print`.
- **A printer installed on the agent's computer:** either type, protocol *System
  printer*, then pick the name from the list (the agent reports the computer's
  printers every minute; start it first) or type it exactly as Windows shows it.

Save, then **Test print**: the test page comes out within a few seconds. The form's
indicator shows what the agent found (*Reachable*, *Problem*, *Agent offline*).

## 4. Tell the app which printer prints what

In the app, **Staff → (profile) → Printing**: next to each print format, choose the
printer under *Orders print on*, *Invoices print on*, *Payment receipts print on*,
*Credit notes print on* and *Shift reports print on*. *Open as PDF* keeps the old
behaviour for that document. The printers strip below shows each printer's state
and has a *Test* button.

Pick a print format made for receipt paper for anything that goes to the Epson
(the shop's *JMCC POS* and *Sales Order POS* formats are; an A4 format is squeezed
onto 72 mm and looks like it).

Then, on a phone, *Print* on an order, invoice, payment or shift report sends it to
the printer. The toast says *Sent to Epson* and then *Printed*, or shows the
printer's error; *Open PDF* is always one tap away in the toast.

## How it works

Every ~2 s the agent POSTs to `sales_pwa.sales_app.printing.agent_poll` with the
token in `X-Sales-Print-Token`. The reply lists the agent's printers and up to five
queued jobs, each already rendered (base64), which the server marks *Sent*. The
agent pushes each job to its printer (raw TCP, or an IPP Print-Job over HTTP) and
POSTs `agent_report` with the outcome: the job becomes *Printed* or *Failed* with
the error, and the phone's toast follows. Every minute the agent also checks each
printer answers on its port (or, for a system printer, that the computer still lists
it), sends the list of the computer's printers, and reports all that, which is what
the desk and the Staff screen show as the printer's state.

A job the agent took but never answered (the agent died mid-job) is offered again
after two minutes, three times, then fails. Jobs are kept for a week (**Sales Print
Job** in the desk: status, error, *Print again*).

Environment: `SP_SERVER_URL`, `SP_AGENT_TOKEN` (required); `SP_POLL_MS`,
`SP_CHECK_MS`, `SP_LOG_LEVEL`, `SP_SUMATRA` (optional). The token never appears on the command
line: it is read from the environment or `.env`.

## Troubleshooting

- **Agent shows Offline in the desk:** the agent is not running, or cannot reach the
  site URL, or the token is wrong (the log says `401 Unknown agent token`).
- **Printer shows "Unreachable":** the agent runs but nothing answers on the
  printer's IP and port. Check the address, that the printer is on and on the same
  network, and that raw printing (port 9100) or IPP is enabled in the printer's own
  web page.
- **Brother prints nothing, job Failed with an IPP status:** try path `/ipp/print`
  versus `/ipp`, and check the printer's web page lists *AirPrint* or *IPP* as
  enabled. A printer that rejects `application/pdf` needs a driver: switch it to
  Raw only if its manual says it prints PDF natively.
- **Receipt text too small or too big:** adjust *Scale* on the printer, or pick a
  format designed for 80 mm.
- **System printer job fails with "SumatraPDF.exe is needed":** download SumatraPDF
  and put the `.exe` next to `agent.mjs`, then print again from the job in the desk.
- **System printer shows "no printer named ...":** the name must match the
  computer's list exactly (pick it from the dropdown on the Sales Printer form).
  On Linux, `lpstat -e` lists the CUPS queues.

Tests: `npm test` (fake printers and a fake server; no network).
