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

The app serves two kinds of field staff from one PWA, chosen per **Sales Profile** (Settings → Sales Profiles in the app, or the Sales Profile doctype):

- **Van Sales** — drivers with stock on board: orders, invoicing, delivery, returns, van loading, stock dashboard, and cash shifts. By default each van has its own warehouse, loaded from the main warehouse; switch off **Separate Van Warehouse** on the profile for a van that sells straight from the main warehouse (stock loading is then hidden and orders, invoices, returns and the stock dashboard use the main warehouse).
- **Field Sales** — order takers without a van: orders and payments only; the back office invoices and delivers. An optional stock warehouse gives them read-only quantities. Shifts are optional.

Shifts work like POS Awesome's: an opening float per payment mode, expenses and cash deposits to the office recorded from the drawer (each posted as a Journal Entry), and a closing that counts every mode against the expected amount. Closings are aggregated by the shift's time window (driver + creation time), never by stamping ERPNext documents. A per-profile **variance tolerance** flags closings that are off (it never blocks); managers can close or reopen any shift.

**Invoice options** (Settings → Invoice options in the app, or the Sales Invoice Option doctype) are named ways of raising an invoice, each with its own Sales Invoice naming series and tax template (blank = no tax). Each option also carries a payment rule: available for credit invoices or not, and for which paid-now modes of payment (empty = every mode). A Sales Profile lists the options its staff may use and marks one default. When staff create an invoice from an order they see only the options that fit the payment choice they made, pick one, see the proposed invoice number (the series' next counter, read without consuming it, so it can still move on) plus subtotal, tax lines and grand total computed by ERPNext, and confirm. A profile without options invoices as before.

The profile also carries the POS-style staff controls: max discount %, the customer's own price list, zero rated items, credit sales, returns and their validity window, hiding out-of-stock items, customer balance visibility, creating customers (and duplicate names), blind cash counts, manager-only closing, and staff cancelling their own cash movements. All are enforced server-side; managers are exempt.

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
