export interface UserSession {
  user: string;
  full_name: string;
  roles?: string[];
  is_manager?: boolean;
  is_driver?: boolean;
  driver_config?: DriverConfig | null;
  capabilities?: Capabilities;
}

export type ProfileType = 'Van Sales' | 'Field Sales' | 'Counter Sales';

/**
 * What the app lets this staff member do, computed server-side from their Van
 * Profile (utils._capabilities). Screens and buttons gate on these flags, never on
 * profile_type directly, and the endpoints enforce the same flags.
 */
export interface Capabilities {
  is_field_sales: boolean;
  /** Counter Sales: a cashier at a PC keying orders in on the Counter screen. */
  is_counter_sales: boolean;
  /** The Counter screen (fast keyboard entry). Managers pass without a profile. */
  can_counter_sell: boolean;
  /** The Counter's Purchase screen (Sales Profile.allow_counter_purchase). Managers pass. */
  can_counter_purchase: boolean;
  /** Expenses paid from the shift's drawer (shifts on and Sales Profile.allow_expense). */
  can_record_expense: boolean;
  /** Van Sales with its own warehouse (loaded from the main one). Off: sells from the main warehouse. */
  has_van_warehouse: boolean;
  can_invoice: boolean;
  can_deliver: boolean;
  can_return: boolean;
  can_load_stock: boolean;
  can_view_stock: boolean;
  uses_shifts: boolean;
  requires_open_shift: boolean;
  /** Profile switches (POS-profile style controls). */
  can_credit_sale: boolean;
  can_create_customer: boolean;
  can_close_shift: boolean;
  can_cancel_cash_movement: boolean;
  shows_customer_balance: boolean;
  blind_shift_close: boolean;
}

// The runtime driver config served in UserSession. It is derived entirely from
// the driver's assigned Sales Profile (see get_van_profile_for_driver on the
// backend) — `name` is the Sales Profile name. There is no separate Driver
// Configuration record; Sales Profile is the single source of truth.
export interface DriverConfig {
  name: string;
  profile_name?: string;
  profile_type?: ProfileType;
  company: string;
  /** Van Sales only. Field Sales profiles carry neither warehouse. */
  separate_van_warehouse?: boolean;
  source_warehouse: string | null;
  van_warehouse: string | null;
  /** What orders, invoices and returns run against: the van warehouse, or the main one for a van without its own. */
  selling_warehouse?: string | null;
  /** Field Sales only: catalog qty is read from here for display. */
  stock_warehouse?: string | null;
  /** Counter Sales: every new sale on the Counter starts on this customer. */
  default_customer?: string | null;
  default_customer_name?: string | null;
  allow_counter_purchase?: boolean;
  buying_price_list?: string | null;
  purchase_taxes_and_charges?: string | null;
  /** The Mode of Payment treated as the cash drawer; the Counter starts on it. */
  default_cash_mode?: string | null;
  /** Resolved invoice options (numbering + tax) this staff member may pick when invoicing. */
  invoice_options?: InvoiceOption[];
  delivery_route?: string;
  daily_credit_limit: number;
  low_stock_threshold: number;
  allow_offline_stock_dashboard: boolean;
  is_active: boolean;
  allowed_payment_modes: string[];
  selling_price_list?: string;
  currency?: string;
  taxes_and_charges?: string;
  apply_discount_on?: string;
  allow_rate_change?: boolean;
  allow_discount_change?: boolean;
  allow_sale_without_stock?: boolean;
  use_shifts?: boolean;
  require_open_shift?: boolean;
  variance_tolerance?: number;
  validate_stock_on_save?: boolean;
  ignore_pricing_rule?: boolean;
  disable_rounded_total?: boolean;
  /** Print formats the app prints with (see Sales Profile → Printing). Blank = the doctype's default. */
  order_print_format?: string;
  invoice_print_format?: string;
  /** Credit notes; blank = the invoice format. */
  return_print_format?: string;
  payment_print_format?: string;
  /** Sales Printers each document goes to on Print (Staff → Printing). Blank = the PDF opens here. */
  order_printer?: string | null;
  invoice_printer?: string | null;
  /** Credit notes; blank = the invoice printer. */
  return_printer?: string | null;
  payment_printer?: string | null;
  shift_report_printer?: string | null;
  letter_head?: string;
  /** Formats staff may pick when printing; a doctype with none listed allows every format. */
  allowed_print_formats?: string[];
  income_account?: string;
  expense_account?: string;
  cost_center?: string;
  write_off_account?: string;
  // POS-profile style controls
  max_discount_percent?: number;
  use_customer_price_list?: boolean;
  allow_zero_rated_items?: boolean;
  allow_credit_sale?: boolean;
  allow_return?: boolean;
  return_validity_days?: number;
  hide_unavailable_items?: boolean;
  show_customer_balance?: boolean;
  allow_create_customer?: boolean;
  allow_duplicate_customer_names?: boolean;
  hide_expected_amount?: boolean;
  allow_driver_close_shift?: boolean;
  allow_cancel_cash_movement?: boolean;
  capabilities?: Capabilities;
}

export interface SalesProfileDriver {
  driver_user: string;
  driver_full_name?: string;
}

export interface ShiftBalanceDetail {
  mode_of_payment: string;
  opening_amount: number;
}

export interface ActiveShift {
  name: string;
  driver: string;
  shift_date: string;
  status: string;
  company?: string;
  van_profile?: string | null;
  period_start: string | null;
  /** Set once closed; the shift's activity is everything created between period_start and period_end. */
  period_end?: string | null;
  closing_shift?: string | null;
  opening_float: number;
  balance_details: ShiftBalanceDetail[];
  notes?: string;
  /** Opened on an earlier day and never closed — must be closed before a new shift. */
  is_stale?: boolean;
}

export type VarianceStatus = 'Balanced' | 'Within Tolerance' | 'Exceeds Tolerance';

export interface ShiftTaxRow {
  account_head: string;
  rate: number;
  amount: number;
}

/** A draft Sales Order made during the shift and not submitted: not in any total. */
export interface ShiftDraftOrder {
  name: string;
  customer: string;
  customer_name: string | null;
  grand_total: number;
  creation: string;
}

/** Submitted activity on the shift's date from before the shift opened, claimed by no closing. */
export interface OutsideWindow {
  orders_count: number;
  orders_total: number;
  payments_count: number;
  payments_total: number;
}

export interface PaymentReconciliationRow {
  mode_of_payment: string;
  opening_amount: number;
  /** null on a blind count (Sales Profile.hide_expected_amount). */
  expected_amount: number | null;
  closing_amount: number;
  difference: number | null;
}

export interface ShiftClosingSummary {
  /** The driver counts without seeing expected amounts (Sales Profile.hide_expected_amount). */
  blind: boolean;
  opening_shift: string;
  driver: string;
  driver_name: string;
  shift_date: string;
  /** Opened on an earlier day and never closed. */
  is_stale: boolean;
  period_start: string | null;
  payment_reconciliation: PaymentReconciliationRow[];
  total_sales: number;
  net_total: number;
  total_taxes: number;
  total_quantity: number;
  total_returns: number;
  taxes: ShiftTaxRow[];
  total_collections: number;
  total_expenses: number;
  /** Cash handed to the office mid-shift (Sales Cash Movement, type Deposit). */
  total_deposits: number;
  /** Purchase Orders submitted on the Counter during the shift (reported, not in the drawer). */
  total_purchases: number;
  /** Paid to suppliers during the shift; each mode's expected amount is already net of it. */
  total_supplier_payments: number;
  /** Overall shift on a counter: counted cash its linked staff handed over at their closings. */
  total_handover: number;
  /** Linked staff's orders (from their closings, or directly for staff without shifts). */
  total_linked_sales: number;
  /** Payments collected by linked staff without shifts, counted on this shift. */
  total_linked_collections: number;
  linked: { handovers: LinkedHandover[]; open_shifts: LinkedOpenShift[] };
  /** A linked van or field rep: the counter profile their counted cash goes to. */
  handover_to: string | null;
  total_opening_float: number;
  expected_cash: number | null;
  /** From the Sales Profile; a net difference beyond it is flagged, never blocked. */
  variance_tolerance: number;
  draft_orders: ShiftDraftOrder[];
  outside_window: OutsideWindow;
}

// ─── Cash movements (cash_movement.py) ───────────────────────────────────────

export type CashMovementType = 'Expense' | 'Deposit';

export interface CashMovement {
  name: string;
  movement_type: CashMovementType;
  amount: number;
  posting_date: string;
  driver: string;
  opening_shift: string;
  expense_account: string | null;
  source_account: string;
  target_account: string;
  against_name: string | null;
  remarks: string | null;
  journal_entry: string | null;
  docstatus: number;
  creation: string;
}

export interface CashMovementContext {
  opening_shift: string | null;
  allow_expense: boolean;
  allow_cash_deposit: boolean;
  require_remarks: boolean;
  max_amount: number;
  cash_account: string | null;
  back_office_cash_account: string | null;
  default_expense_account: string | null;
  expense_accounts: Array<{ name: string; account_name: string }>;
  movements: CashMovement[];
}

export interface SalesProfile {
  name: string;
  profile_name: string;
  profile_type: ProfileType;
  company: string;
  is_active: boolean;
  delivery_route?: string;
  default_cash_mode?: string;
  selling_price_list?: string;
  currency?: string;
  separate_van_warehouse: boolean;
  source_warehouse: string | null;
  van_warehouse: string | null;
  stock_warehouse?: string | null;
  /** Counter Sales: the customer every new sale on the Counter starts on. */
  default_customer?: string | null;
  default_customer_name?: string | null;
  /** Counter Sales: the Purchase screen, and where its rates and taxes come from. */
  allow_counter_purchase?: boolean;
  buying_price_list?: string | null;
  purchase_taxes_and_charges?: string | null;
  /** Counter Sales: Van and Field Sales profiles that hand over to this counter (the overall shift). */
  linked_profiles?: string[];
  assigned_drivers: SalesProfileDriver[];
  allowed_payment_modes: string[];
  allowed_customer_groups: string[];
  taxes_and_charges?: string;
  apply_discount_on: string;
  daily_credit_limit: number;
  low_stock_threshold: number;
  allow_rate_change: boolean;
  allow_discount_change: boolean;
  allow_sale_without_stock: boolean;
  use_shifts: boolean;
  require_open_shift: boolean;
  variance_tolerance?: number;
  validate_stock_on_save: boolean;
  allow_offline_stock_dashboard: boolean;
  ignore_pricing_rule: boolean;
  disable_rounded_total: boolean;
  /** Print formats the app prints with (see Sales Profile → Printing). Blank = the doctype's default. */
  order_print_format?: string;
  invoice_print_format?: string;
  /** Credit notes; blank = the invoice format. */
  return_print_format?: string;
  payment_print_format?: string;
  /** Sales Printers each document goes to on Print. Blank = the PDF opens on the phone. */
  order_printer?: string | null;
  invoice_printer?: string | null;
  return_printer?: string | null;
  payment_printer?: string | null;
  shift_report_printer?: string | null;
  letter_head?: string;
  /** Formats staff may pick when printing; a doctype with none listed allows every format. */
  allowed_print_formats?: string[];
  income_account?: string;
  expense_account?: string;
  cost_center?: string;
  write_off_account?: string;
  // Cash movements (expenses & deposits from the drawer)
  allow_expense: boolean;
  allow_cash_deposit: boolean;
  cash_account?: string | null;
  back_office_cash_account?: string | null;
  cash_movement_max_amount: number;
  require_cash_movement_remarks: boolean;
  allowed_expense_accounts: string[];
  /** Sales Invoice Options this profile's staff may invoice with; one is the default. */
  invoice_options: Array<{ invoice_option: string; is_default: boolean }>;
  // POS-profile style controls
  max_discount_percent: number;
  use_customer_price_list: boolean;
  allow_zero_rated_items: boolean;
  allow_credit_sale: boolean;
  allow_return: boolean;
  return_validity_days: number;
  hide_unavailable_items: boolean;
  show_customer_balance: boolean;
  allow_create_customer: boolean;
  allow_duplicate_customer_names: boolean;
  hide_expected_amount: boolean;
  allow_driver_close_shift: boolean;
  allow_cancel_cash_movement: boolean;
  capabilities?: Capabilities;
}

export interface SalesProfileOptions {
  warehouses: Array<{ name: string; company: string }>;
  payment_modes: PaymentMode[];
  routes: Array<{ name: string }>;
  customer_groups: Array<{ name: string }>;
  companies: Array<{ name: string; default_currency?: string }>;
  price_lists: Array<{ name: string }>;
  tax_templates: Array<{ name: string; company: string }>;
  /** Counter Sales purchases: buying price lists and purchase tax templates. */
  buying_price_lists?: Array<{ name: string }>;
  purchase_tax_templates?: Array<{ name: string; company: string }>;
  invoice_options: InvoiceOption[];
  currencies: Array<{ name: string }>;
  print_formats: Array<{ name: string; doc_type: string }>;
  /** Active Sales Printers (desk: Sales Printer), reached through a print agent on the shop's LAN. */
  printers: Array<{ name: string; printer_type: PrinterType }>;
  letter_heads: Array<{ name: string; is_default?: number }>;
  users: Array<{ name: string; full_name: string }>;
  cash_accounts: Array<{ name: string; account_name: string; company: string; account_type: string }>;
  expense_accounts: Array<{ name: string; account_name: string; company: string }>;
  cost_centers: Array<{ name: string; company: string }>;
}

export interface DriverSetupOptions {
  users: Array<{ name: string; full_name: string }>;
  warehouses: Array<{ name: string; company: string }>;
  payment_modes: PaymentMode[];
  routes: Array<{ name: string }>;
  companies: Array<{ name: string; default_currency?: string }>;
}


export interface Customer {
  name: string;
  customer_name: string;
  customer_group: string;
  territory: string;
  mobile_no?: string | null;
  image?: string;
}

export interface Item {
  item_code: string;
  item_name: string;
  description: string;
  stock_uom: string;
  /** stock_uom is a whole-number UOM (Nos, Box, ...): no fractional quantities. */
  must_be_whole_number?: boolean;
  image?: string;
  item_group: string;
  standard_rate?: number;
  price_list_rate?: number;
  actual_qty?: number;
  has_batch_no?: boolean;
  has_serial_no?: boolean;
}

export interface ItemSalesHistoryRow {
  sales_order: string;
  transaction_date: string;
  customer: string;
  customer_name: string;
  qty: number;
  rate: number;
  amount: number;
}

export interface InvoiceStockShortage {
  item_code: string;
  item_name: string;
  stock_uom: string;
  required_qty: number;
  available_qty: number;
  short_qty: number;
}

export interface InvoiceStockCheck {
  allow_sale_without_stock: boolean;
  short_items: InvoiceStockShortage[];
}

/** A way of raising an invoice: numbering series + tax template (Sales Invoice Option master). */
export interface InvoiceOption {
  name: string;
  option_name: string;
  naming_series: string;
  taxes_and_charges: string | null;
  company?: string | null;
  description?: string | null;
  disabled?: boolean;
  /** Set on a profile's list: pre-selected for its staff. */
  is_default?: boolean;
  /** Payment rule: offered for credit (pay later) invoices? */
  available_for_credit: boolean;
  /** Payment rule: offered when paid now with one of these modes. Empty = every mode. */
  payment_modes: string[];
}

/** Does the option's payment rule fit this payment choice? Mirrors invoice_option.option_applies(). */
export function invoiceOptionApplies(option: InvoiceOption, markAsPaid: boolean, modeOfPayment: string | null | undefined): boolean {
  if (!markAsPaid) return option.available_for_credit !== false;
  const modes = option.payment_modes || [];
  return modes.length === 0 || (!!modeOfPayment && modes.includes(modeOfPayment));
}

export interface InvoiceOptionChoices {
  naming_series: string[];
  tax_templates: Array<{ name: string; company: string }>;
  companies: Array<{ name: string }>;
  payment_modes: PaymentMode[];
}

export interface InvoicePreviewLine {
  item_code: string;
  item_name: string;
  qty: number;
  uom: string;
  rate: number;
  amount: number;
}

export interface InvoicePreviewTax {
  description: string;
  rate: number;
  tax_amount: number;
  included_in_print_rate: boolean;
}

/** preview_sales_invoice(): what create_sales_invoice() would raise, nothing saved. */
export interface InvoicePreview {
  sales_order: string;
  customer: string;
  customer_name: string;
  posting_date: string;
  currency: string;
  invoice_option: InvoiceOption | null;
  naming_series: string | null;
  /** The series' next number, read without consuming it. May move on before Confirm. */
  proposed_name: string | null;
  taxes_and_charges: string | null;
  items: InvoicePreviewLine[];
  total_qty: number;
  total: number;
  net_total: number;
  discount_amount: number;
  taxes: InvoicePreviewTax[];
  total_taxes_and_charges: number;
  grand_total: number;
  rounding_adjustment: number;
  rounded_total: number;
  disable_rounded_total: boolean;
  short_items: InvoiceStockShortage[];
  allow_sale_without_stock: boolean;
  /** The order is re-taxed to the option on confirm, so its total matches the invoice. */
  order_grand_total: number;
  order_taxes_will_update: boolean;
}

export interface CartLine {
  item: Item;
  qty: number;
  rate?: number;
}

export interface SalesOrderItem {
  item_code: string;
  item_name: string;
  qty: number;
  rate: number;
  amount: number;
  delivery_date?: string;
  stock_uom?: string;
  price_list_rate?: number;
}

export interface SalesOrder {
  name: string;
  customer: string;
  customer_name: string;
  transaction_date: string;
  modified?: string;
  grand_total: number;
  total_taxes_and_charges?: number;
  status: string;
  owner: string;
  docstatus: number;
  items: SalesOrderItem[];
  selling_price_list?: string;
  company?: string;
  delivery_date?: string;
  naming_series?: string;
  order_type?: string;
  per_billed?: number;
  per_delivered?: number;
  additional_discount_percentage?: number;
  discount_amount?: number;
  apply_discount_on?: string;
}
/** A submitted Sales Invoice raised from an order (sales.get_order_invoices). */
export interface OrderInvoice {
  name: string;
  posting_date: string;
  grand_total: number;
  outstanding_amount: number;
  is_return: boolean;
  status: string;
}

export interface OutstandingInvoice {
  name: string;
  posting_date: string;
  grand_total: number;
  outstanding_amount: number;
  allocated_amount?: number; // UI state
  checked?: boolean; // UI state
}

export interface PaymentReference {
  name: string;
  grand_total: number;
  outstanding_amount: number;
  allocated_amount: number;
}

export interface LedgerEntry {
  posting_date: string;
  voucher_type: string;
  voucher_no: string;
  debit: number;
  credit: number;
  account: string;
}

export interface PaymentMode {
  name: string;
  type: string;
}

export interface SalesOrderSummary {
  name: string;
  transaction_date: string;
  grand_total: number;
  advance_paid: number;
}

export interface CustomerSummary {
  outstanding_balance: number;
  last_invoice?: {
    name: string;
    posting_date: string;
    grand_total: number;
  };
  last_payment?: {
    name: string;
    posting_date: string;
    paid_amount: number;
  };
}

export interface DriverStockItem {
  item_code: string;
  item_name: string;
  stock_uom: string;
  image?: string;
  actual_qty: number;
  reserved_qty: number;
  projected_qty: number;
  has_batch_no: boolean;
  has_serial_no: boolean;
  is_low_stock: boolean;
}

export interface DriverStockDashboard {
  warehouse: string;
  /** Null for a van that sells straight from the main warehouse (nothing is loaded). */
  source_warehouse: string | null;
  company: string;
  low_stock_threshold: number;
  generated_at: string;
  summary: {
    item_count: number;
    low_stock_count: number;
    total_available_qty: number;
    total_reserved_qty: number;
  };
  items: DriverStockItem[];
}

export interface TransferItemDetail {
  item_code: string;
  item_name: string;
  description?: string;
  stock_uom: string;
  image?: string;
  has_batch_no: boolean;
  has_serial_no: boolean;
  source_warehouse: string;
  van_warehouse: string;
  source_qty: number;
  van_qty: number;
  batches: Array<{
    batch_no: string;
    available_qty: number;
  }>;
  serial_nos: string[];
}

export interface StockTransferLine {
  item_code: string;
  item_name: string;
  stock_uom: string;
  qty: number;
  batch_no?: string;
  serial_nos?: string[];
  available_qty: number;
  has_batch_no: boolean;
  has_serial_no: boolean;
}

export interface ShiftReportReconciliationRow {
  mode_of_payment: string;
  opening_amount: number;
  expected_amount: number;
  /** Counted / difference only exist on a closing report — an open shift hasn't been counted. */
  closing_amount: number | null;
  difference: number | null;
}

export interface ShiftReportItem {
  item_code: string;
  item_name: string;
  uom: string;
  sold_qty: number;
  sold_amount: number;
  returned_qty: number;
  returned_amount: number;
  net_qty: number;
}

/** Shift summary (open shift snapshot) or closing report (closed shift) — see shift_report.py. */
export interface ShiftReport {
  report_type: 'summary' | 'closing';
  generated_at: string;
  shift: {
    opening_shift: string;
    closing_shift: string | null;
    driver: string;
    driver_name: string;
    van_profile: string | null;
    company: string;
    currency: string | null;
    shift_date: string;
    period_start: string | null;
    period_end: string | null;
    status: string;
    closed_by?: string | null;
    closed_by_name?: string | null;
    notes: string | null;
  };
  totals: {
    total_sales: number;
    net_total: number;
    total_taxes: number;
    total_quantity: number;
    total_returns: number;
    variance_tolerance?: number;
    variance_status?: VarianceStatus;
    draft_orders_count?: number;
    total_collections: number;
    total_expenses: number;
    total_deposits: number;
    total_purchases?: number;
    total_supplier_payments?: number;
    total_handover?: number;
    total_linked_sales?: number;
    total_linked_collections?: number;
    purchases_count?: number;
    supplier_payments_count?: number;
    total_opening_float: number;
    expected_cash: number;
    net_difference?: number;
    sales_orders_count: number;
    invoices_count: number;
    invoiced_total: number;
    returns_count: number;
    returns_total: number;
    net_invoiced: number;
    payments_count: number;
    expenses_count: number;
    deposits_count: number;
  };
  /** Drawer mode expenses and deposits are deducted from; null when the shift has no cash mode. */
  cash_mode: string | null;
  /** The documents behind the totals, for drilling down from a tile. */
  documents: {
    orders: ShiftReportOrder[];
    invoices: ShiftReportInvoice[];
    payments: ShiftReportPayment[];
    /** Purchase Orders raised on the Counter, with the bill each turned into. */
    purchases?: ShiftReportPurchase[];
  };
  payment_reconciliation: ShiftReportReconciliationRow[];
  collections: Array<{ mode_of_payment: string; count: number; amount: number }>;
  taxes: ShiftTaxRow[];
  /** Legacy expense logs and cash movements of type Expense; expense_type is the account name for the latter. */
  expenses: ShiftReportCashRow[];
  deposits: ShiftReportCashRow[];
  /** Pay Payment Entries to suppliers: already deducted from their mode's expected amount. */
  supplier_payments?: ShiftReportPayment[];
  /** Overall shift on a counter: what its linked staff handed over or rolled in. */
  linked?: ShiftReportLinked;
  items: ShiftReportItem[];
  /** Only on a summary: drafts can still be submitted while the shift is open. */
  draft_orders: ShiftDraftOrder[];
}

export interface ShiftReportOrder {
  name: string;
  customer: string;
  customer_name: string | null;
  grand_total: number;
  total_qty: number;
  status: string;
  creation: string;
}

export interface ShiftReportInvoice {
  name: string;
  customer: string;
  customer_name: string | null;
  /** Always positive; is_return tells a credit note apart. */
  amount: number;
  is_return: 0 | 1;
  status: string;
  creation: string;
}

export interface ShiftReportPayment {
  name: string;
  party: string;
  party_name: string | null;
  mode_of_payment: string;
  amount: number;
  creation: string;
}

export interface LinkedHandover {
  closing: string;
  opening_shift: string;
  driver: string;
  driver_name: string;
  profile: string;
  shift_date: string;
  period_end?: string | null;
  total_sales: number;
  total_collections: number;
  /** What they counted at their closing, all modes. */
  handed_over: number;
  net_difference: number;
  by_mode: Array<{ mode_of_payment: string; amount: number }>;
}

export interface LinkedOpenShift {
  opening_shift: string;
  driver: string;
  driver_name: string;
  profile: string;
  shift_date: string;
  period_start: string | null;
}

export interface LinkedDirect {
  driver: string;
  driver_name: string;
  profile: string | null;
  orders_count: number;
  sales_total: number;
  payments_count: number;
  collections_total: number;
  by_mode: Array<{ mode_of_payment: string; amount: number }>;
}

export interface ShiftReportLinked {
  handovers: LinkedHandover[];
  direct: LinkedDirect[];
  open_shifts: LinkedOpenShift[];
  /** The part of it that went into the counter's drawer (cash-type modes). */
  drawer_amount: number;
  cash_mode: string | null;
  total_handover: number;
  total_linked_sales: number;
  total_linked_collections: number;
}

export interface ShiftReportPurchase {
  name: string;
  supplier: string;
  supplier_name: string | null;
  amount: number;
  invoice: string | null;
  status: string;
  creation: string;
}

export interface ShiftReportCashRow {
  name: string;
  expense_type: string;
  notes: string | null;
  amount: number;
  journal_entry: string | null;
}

export interface ShiftClosingListRow {
  name: string;
  opening_shift: string;
  driver: string;
  driver_name: string;
  shift_date: string;
  period_start: string | null;
  period_end: string | null;
  total_sales: number;
  total_collections: number;
  net_difference: number;
  variance_status?: VarianceStatus | null;
  closed_by?: string | null;
  draft_orders_count?: number;
}

// ─── Manager reports (manager_report.py) ─────────────────────────────────────

export interface FleetTotals {
  orders_count: number;
  sales: number;
  invoices_count: number;
  invoiced: number;
  returns_count: number;
  returns: number;
  payments_count: number;
  collections: number;
  expenses_count: number;
  expenses: number;
  deposits_count?: number;
  deposits?: number;
  shifts_count: number;
  variance: number;
  variance_shifts: number;
  /** Closings whose variance exceeds the profile tolerance. */
  flagged_shifts?: number;
  draft_orders?: number;
  net_sales: number;
  net_cash: number;
  avg_order: number;
  return_rate: number;
}

export interface FleetDriverInfo {
  driver: string;
  driver_name: string;
  van_profile: string;
  van_name: string;
  profile_type?: ProfileType;
  delivery_route?: string | null;
  uses_shifts?: boolean;
}

export type FleetDriverRow = FleetDriverInfo & FleetTotals;

export interface ManagerDashboardVan extends FleetDriverRow {
  shift_status: 'open' | 'closed' | 'stale' | 'none';
  opening_shift: string | null;
  closing_shift: string | null;
  shift_since: string | null;
  expected_cash: number | null;
  net_difference: number | null;
  variance_status?: VarianceStatus | null;
  draft_orders_count?: number;
}

export interface ManagerAlert {
  level: 'warning' | 'danger' | 'info';
  kind: 'stale_shift' | 'variance' | 'no_shift' | 'draft_orders';
  driver: string;
  reference: string | null;
  title: string;
  body: string;
  amount?: number;
}

export interface ManagerDashboard {
  date: string;
  totals: FleetTotals & { open_shifts?: number; closed_shifts?: number; expected_cash_open?: number };
  vans: ManagerDashboardVan[];
  alerts: ManagerAlert[];
}

export interface PeriodComparisonRow {
  metric: keyof FleetTotals;
  label: string;
  current: number;
  previous: number;
  delta: number;
  delta_pct: number | null;
}

export interface PeriodDailyRow {
  date: string;
  sales: number;
  collections: number;
  expenses: number;
  returns: number;
}

export interface PeriodItemRow {
  item_code: string;
  item_name: string;
  item_group: string | null;
  uom: string;
  sold_qty: number;
  sold_amount: number;
  returned_qty: number;
  returned_amount: number;
  net_qty: number;
  net_amount: number;
}

export interface PeriodShiftRow {
  name: string;
  opening_shift: string;
  driver: string;
  driver_name: string;
  van_name?: string | null;
  shift_date: string;
  period_start: string | null;
  period_end: string | null;
  total_sales: number;
  total_collections: number;
  total_expenses: number;
  expected_cash: number;
  net_difference: number;
  variance_status?: VarianceStatus | null;
  variance_tolerance?: number;
  draft_orders_count?: number;
  closed_by?: string | null;
}

export interface PeriodReport {
  period: { from_date: string; to_date: string; days: number; previous_from: string; previous_to: string };
  totals: FleetTotals;
  previous: FleetTotals;
  comparison: PeriodComparisonRow[];
  daily: PeriodDailyRow[];
  by_driver: FleetDriverRow[];
  collections_by_mode: Array<{ mode_of_payment: string; count: number; amount: number }>;
  expenses_by_type: Array<{ expense_type: string; count: number; amount: number }>;
  items: PeriodItemRow[];
  item_groups: Array<{ item_group: string; sold_amount: number; returned_amount: number; net_amount: number; items: number }>;
  customers: Array<{ customer: string; customer_name: string; orders_count: number; sales: number }>;
  shifts: PeriodShiftRow[];
}

export interface FleetOptions {
  drivers: FleetDriverInfo[];
  vans: Array<{ van_profile: string; van_name: string }>;
}

// ─── Direct printing (sales_pwa.sales_app.printing) ───────────────────────────

export type PrinterType = 'Receipt (ESC/POS)' | 'Document (PDF)';

/** What print_document returns: the queued job, or job: null when the PDF should open instead. */
export interface PrintJobReceipt {
  job: string | null;
  printer?: string;
  printer_type?: PrinterType;
  /** The printer's agent has polled in the last few minutes. */
  online?: boolean;
}

/** print_choices: what the print setup sheet offers for one doctype. */
export interface PrintChoices {
  doctype: string;
  /** "Standard" first, then the enabled formats of the doctype. */
  formats: Array<{ name: string }>;
  /** What the profile picks when nothing is chosen; null when the profile allows no enabled format. */
  default_format: string | null;
  /** Active printers whose agent is switched on; `online` = the agent polled in the last few minutes. */
  printers: Array<{ name: string; printer_type: PrinterType; online: boolean }>;
  default_printer: string | null;
}

export interface PrintJobStatus {
  job: string;
  status: 'Queued' | 'Sent' | 'Printed' | 'Failed';
  error: string;
  printer: string;
  attempts: number;
}

/** A row of printer_status (managers): one active printer and how its agent is doing. */
export interface PrinterStatusRow {
  name: string;
  printer_type: PrinterType;
  host: string;
  port: number;
  protocol: string;
  /** The queue name on the agent's computer, for a System printer. */
  system_printer: string;
  paper_width?: string;
  agent: string;
  agent_active: boolean;
  agent_online: boolean;
  agent_host: string;
  last_status: string;
  last_contact_at: string | null;
  waiting: number;
  failed_today: number;
}

// ─── Counter (fast keyboard order entry on a PC) ─────────────────────────────

/** search_counter_items(): an item with everything the entry row needs. */
export interface CounterItem {
  item_code: string;
  item_name: string;
  item_group: string;
  stock_uom: string;
  must_be_whole_number: boolean;
  is_stock_item: boolean;
  has_batch_no: boolean;
  has_serial_no: boolean;
  /** From the price list the order will be priced with, else Item.standard_rate. */
  price_list_rate: number;
  standard_rate: number;
  /** Stock in the selling warehouse; null when the counter has no warehouse to read. */
  actual_qty: number | null;
  /** The typed text is exactly this item's code or barcode. */
  exact: boolean;
}

export interface CounterSearchResult {
  items: CounterItem[];
  price_list: string | null;
  warehouse: string | null;
}

/** A line on the Counter. Lines are independent: the same item can appear twice. */
export interface CounterLine {
  uid: string;
  item: CounterItem;
  qty: number;
  rate: number;
}

/** preview_counter_totals(): what ERPNext would put on the order for the cart as it stands. */
export interface CounterPreview {
  customer: string;
  lines: InvoicePreviewLine[];
  total_qty: number;
  total: number;
  net_total: number;
  discount_amount: number;
  taxes: InvoicePreviewTax[];
  total_taxes_and_charges: number;
  grand_total: number;
  rounding_adjustment: number;
  rounded_total: number;
  disable_rounded_total: boolean;
  taxes_and_charges: string | null;
  invoice_option: InvoiceOption | null;
  /** The series' next number, read without consuming it. May move on before confirm. */
  proposed_invoice_name: string | null;
  short_items: InvoiceStockShortage[];
  allow_sale_without_stock: boolean;
  warehouse: string | null;
  /** The profile refuses this cart as it stands (rate, discount or zero-rated rule). */
  error: string | null;
}

/** create_counter_sale(): the submitted order and, when asked for, the invoice. */
export interface CounterSaleResult {
  order: string;
  customer: string;
  customer_name: string | null;
  order_grand_total: number;
  invoice: string | null;
  grand_total: number;
  rounded_total: number;
  outstanding_amount: number | null;
  short_items: InvoiceStockShortage[];
}

export interface CounterQueueOrder {
  name: string;
  customer: string;
  customer_name: string | null;
  transaction_date: string;
  grand_total: number;
  total_qty: number;
  status: string;
  creation: string;
  modified: string;
}

export interface CounterQueueInvoice {
  name: string;
  customer: string;
  customer_name: string | null;
  grand_total: number;
  rounded_total: number;
  outstanding_amount: number;
  status: string;
  creation: string;
}

/** get_counter_queue(): the cashier's own worklist for the side panel. */
export interface CounterQueue {
  held: CounterQueueOrder[];
  to_invoice: CounterQueueOrder[];
  invoices_today: CounterQueueInvoice[];
}

// ─── Counter purchases (counter_purchase.py) ─────────────────────────────────

export interface Supplier {
  name: string;
  supplier_name: string;
  supplier_group: string | null;
  mobile_no: string | null;
}

export interface PurchaseContext {
  warehouse: string | null;
  price_list: string | null;
  taxes_and_charges: string | null;
  /** The site makes Supplier Invoice No mandatory on a Purchase Invoice. */
  bill_no_required: boolean;
}

export interface PurchasePreview {
  error: string | null;
  lines: Array<{ item_code: string; item_name: string; qty: number; uom: string; rate: number; amount: number }>;
  total_qty: number;
  total: number;
  net_total?: number;
  taxes: Array<{ description: string; rate: number; tax_amount: number; included_in_print_rate: boolean }>;
  total_taxes_and_charges?: number;
  grand_total: number;
  rounding_adjustment?: number;
  rounded_total: number;
  disable_rounded_total?: boolean;
  taxes_and_charges?: string | null;
  warehouse: string | null;
  price_list: string | null;
}

export interface PurchaseOrderResult {
  order: string;
  docstatus: number;
  supplier: string;
  supplier_name: string | null;
  grand_total: number;
  rounded_total: number;
}

export interface PurchaseOrderDetail extends PurchaseOrderResult {
  per_billed: number;
  items: Array<{ item_code: string; item_name: string; qty: number; rate: number; stock_uom: string; uom: string }>;
}

export interface PurchaseBillResult {
  order: string;
  invoice: string;
  supplier: string;
  supplier_name: string | null;
  grand_total: number;
  rounded_total: number;
  outstanding_amount: number;
  payment: string | null;
}

export interface PurchaseQueueOrder {
  name: string;
  supplier: string;
  supplier_name: string | null;
  transaction_date: string;
  grand_total: number;
  total_qty: number;
  status: string;
  creation: string;
  modified: string;
}

export interface PurchaseQueueBill {
  name: string;
  supplier: string;
  supplier_name: string | null;
  grand_total: number;
  rounded_total: number;
  outstanding_amount: number;
  status: string;
  creation: string;
}

export interface PurchaseQueue {
  held: PurchaseQueueOrder[];
  to_bill: PurchaseQueueOrder[];
  bills_today: PurchaseQueueBill[];
}
