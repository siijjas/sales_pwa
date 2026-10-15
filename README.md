### Sales App

Van sales and field sales order app for ERPNext: a mobile PWA for drivers and sales reps with orders, payments, stock, returns and POS-style cash shifts.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app sales_pwa
```

### Setup

The app serves two kinds of field staff from one PWA, chosen per **Sales Profile** (**Staff** in the app, or the Sales Profile doctype):

- **Van Sales** — drivers with stock on board: orders, invoicing, delivery, returns, van loading, stock dashboard, and cash shifts. By default each van has its own warehouse, loaded from the main warehouse; switch off **Separate Van Warehouse** on the profile for a van that sells straight from the main warehouse (stock loading is then hidden and orders, invoices, returns and the stock dashboard use the main warehouse).
- **Field Sales** — order takers without a van: orders and payments only; the back office invoices and delivers. An optional stock warehouse gives them read-only quantities. Shifts are optional.
- **Counter Sales** — a cashier or data entry operator at a PC. They get the **Counter** screen (below) instead of the phone's Sell flow: one screen, keyboard first, selling and invoicing straight from the profile's warehouse. An optional **Default Customer** (a walk-in customer, say) starts every sale so the cashier goes straight to the items. Shifts work as for a van.

**The Counter** (`/counter`, also open to managers) is built for typing, not scanning, though barcodes match too. The customer box takes a name, ID or mobile (F2). The entry row at the head of the lines takes an item code, name or barcode: an exact code adds on Enter without opening the list, otherwise the arrow keys pick from the ranked list; Enter moves to the quantity, Enter again lands the line and returns to the item box (F3). The same item typed twice makes two lines. Quantities and, when the profile allows, rates are edited in place in the grid (arrow keys move between lines, Ctrl+Delete removes one). The totals panel shows what ERPNext will put on the order, re-taxed to the chosen invoice option, with the proposed invoice number and any stock shortage, as the cashier types. Then **Submit order** (F9) submits the Sales Order at once and asks whether to invoice it as well: Enter says yes and walks through how it is paid (paid now with a mode of payment, or credit) and, when the profile has invoice options, which one, then raises the invoice and opens the print sheet (unless the cashier switched that off); Esc leaves the order in the To invoice list. **F7** holds the sale as a draft, **F10** reprints the last invoice, **Esc** clears. The side panel lists the cashier's held orders (Resume), submitted orders still to invoice (Invoice, through the usual invoice sheet) and today's invoices (Print). Every rule on the profile applies as it does on the phone: customer scope, price list, rate and discount controls, zero-rated items, credit sales, shifts, invoice options and stock.

The Counter's **Purchases** tab (`/counter/purchase`; profiles with **Allow Purchase Orders**, on by default for Counter Sales, and managers) keys in a Purchase Order the same way: supplier (F2), then code, qty and the supplier's rate (it starts on the supplier's buying price, then the profile's **Buying Price List**, then the last purchase rate). **Submit** (F9) submits the order into the profile's warehouse and asks whether to bill it now: the supplier's invoice number (required when the site makes it mandatory), paid now from a mode of payment or on credit, then a Purchase Invoice that receives the stock (and a Pay Payment Entry when paid). F7 holds it as a draft; the side panel lists held orders, orders still to bill and today's bills. A **Purchase Taxes and Charges Template** on the profile taxes these orders.

Both Counter screens carry a **shift bar**: open or close the shift, the shift summary, what the drawer should hold now, and **Expense** (F6), a sheet that records an expense from the drawer on the open shift without leaving the screen. Supplier payments made during the shift come off the expected amount of the mode they were paid from, and the closing and its report list the shift's purchases and supplier payments.

**Overall shift.** A Counter Sales profile can list **Linked Profiles** (Van Sales and Field Sales profiles, each linked to one counter only) under *Overall shift* in the profile editor. Their staff then hand over to the counter: staff on shifts when they close theirs (the cash they counted, per mode, is added to the counter's expected amounts: cash-type modes into its drawer, others into the mode of the same name), staff without shifts directly (their orders and payments count on the counter's shift). Only activity from the moment of linking counts, and whatever is handed over while the counter is closed lands on its next shift. The counter's closing and report show each handover and each rep's orders and payments apart from the cashier's own; the close screen and the shift bar warn while a linked shift is still open; a linked driver's close screen names the counter their cash goes to. A van closing handed over to a counter shift that has since closed cannot be reopened until that counter shift is reopened.

Shifts work like POS Awesome's: an opening float per payment mode, expenses and cash deposits to the office recorded from the drawer (each posted as a Journal Entry), and a closing that counts every mode against the expected amount. Closings are aggregated by the shift's time window (driver + creation time), never by stamping ERPNext documents. A per-profile **variance tolerance** flags closings that are off (it never blocks); managers can close or reopen any shift.

**Invoice options** (**Setup → Invoice options** in the app, or the Sales Invoice Option doctype) are named ways of raising an invoice, each with its own Sales Invoice naming series and tax template (blank = no tax). Each option also carries a payment rule: available for credit invoices or not, and for which paid-now modes of payment (empty = every mode). A Sales Profile lists the options its staff may use and marks one default. When staff create an invoice from an order they see only the options that fit the payment choice they made, pick one, see the proposed invoice number (the series' next counter, read without consuming it, so it can still move on) plus subtotal, tax lines and grand total computed by ERPNext, and confirm. A profile without options invoices as before.

**WhatsApp notifications.** The app can announce activity in a WhatsApp group: a new, updated, confirmed or cancelled Sales Order, and a customer payment received or cancelled. Messages go through the Baileys-based gateway in `whatsapp-gateway/` (see its README), configured once under *WhatsApp Settings* in the desk: gateway URL and key, the target group (picked from the paired number's groups), which events to post, and whether to post only what was entered through the app (the default) or desk entries as well. The text of each message is a Jinja template on the same settings page (*Message text*: order and payment), with *Preview messages* to see the result for sample documents and *Reset message text* to start from the built-in wording, which uses WhatsApp bold and italics with a blank line between groups and names the customer, items and amounts but no staff, voucher number or time (`{{ staff }}`, `{{ doc.name }}` and `{{ when }}` bring them back). A template that fails to render is refused on save; one that fails on real data is logged and the built-in text is posted instead. Posting happens after the transaction commits, from a background job, so a dead gateway never blocks a sale; failures land in the Error Log. The scheduler asks the gateway for its state every minute and shows it at the top of the settings (Connected, Not linked, Down, Restricted), with one Error Log entry when the link goes down. New use cases are a message builder plus a `doc_events` line in `sales_pwa/sales_app/whatsapp.py` and `hooks.py`.

**Printing** (the profile's Printing section) names the print format the app uses for each document staff print from a phone: the order, the invoice, the credit note (blank = the invoice format) and the payment receipt, plus a letter head. Blank means the doctype's default format and the company's default letter head. The PDF endpoint renders manager-authored formats unrestricted once the caller is authorized for the document, so a format that lists ledger rows prints for staff who cannot read the ledger themselves; a manager without a profile prints a document the way its owner's profile would.

**Direct printing.** Each document can also go straight to a printer on the shop's LAN instead of opening as a PDF: a receipt printer such as the Epson TM-T20 (the format is rendered as a bitmap and sent as ESC/POS raster, then cut) an office printer such as a Brother laser (the PDF, over IPP), or any printer installed on the agent's computer, USB included (through the Windows spooler, with SumatraPDF for PDFs, or CUPS). The server cannot reach the shop's network, so a dependency-free Node agent in `print-agent/` runs on any computer next to the printers, polls the site with its token, pushes the jobs it gets to the printers and reports back; nothing listens on the LAN. Setup is in the desk (*Sales Print Agent* with its token, then one *Sales Printer* per device with its IP, protocol and paper) and in the app (*Staff → Printing*: which printer each document prints on, printer state, test page). Every Print tap asks: the print sheet lists the enabled formats of the document and the printers whose agent is on, plus *Open as PDF*, marks what the profile would pick, and opens on what that person picked last for the document type (kept in that browser), so Enter alone prints (`print_choices`, and the `printer` argument of `print_document`). The profile's *Allowed Print Formats* (Staff → profile → Printing, *Formats staff may choose*) limits which formats its staff may pick: a document type with formats ticked offers only those plus the profile's own format for it, never Standard, and the server refuses any other (`pdf.allowed_print_formats`); a document type with none ticked, and managers without a profile, keep every enabled format. Jobs are *Sales Print Job* rows (Queued → Sent → Printed / Failed, retried when the agent never answers, purged after a week); the phone's toast follows the job and keeps *Open PDF* one tap away. See `print-agent/README.md`.

The profile also carries the POS-style staff controls: max discount %, the customer's own price list, zero rated items, credit sales, returns and their validity window, hiding out-of-stock items, customer balance visibility, creating customers (and duplicate names), blind cash counts, manager-only closing, and staff cancelling their own cash movements. All are enforced server-side; managers are exempt.

The app has five tabs on a phone (a rail on tablets and desktops): **Home**, **Sell**, **Customers**, then **Stock**, **Reports** or **Activity** depending on the person, and **More**. Selling is one three-step flow (customer, items, review) that ends with "Submit order" or "Submit & invoice"; everything about a customer (balance, collect payment, return, ledger) starts from their page; the shift has its own area. A sale in progress is kept on the device until it is submitted or discarded. The app is online-only.

After pulling changes, migrate and rebuild:

```bash
bench --site <your-site> migrate
cd apps/sales_pwa/frontend && npm run build
```

Enable the bench scheduler on the site if it is not already: the daily `sales_pwa.sales_app.tasks.notify_stale_shifts` job notifies managers of shifts left open from earlier days.

Tests run against a site with ERPNext set up:

```bash
bench --site <your-site> run-tests --app sales_pwa
```

See `PRD.md` for the full screen inventory, doctypes and API modules.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/sales_pwa
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
# sales_pwa
