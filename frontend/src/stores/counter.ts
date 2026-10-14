import { defineStore } from 'pinia';
import type { CounterItem, CounterLine, Customer, SalesOrderItem } from '../types';
import type { DiscountMode } from './sale';

interface CounterState {
  /** Whose cart this is; the cart is persisted per user. */
  user: string | null;
  customer: Customer | null;
  lines: CounterLine[];
  /** Set when a held (draft) Sales Order was resumed: the sale updates it instead of creating one. */
  orderName: string | null;
  discountMode: DiscountMode;
  discountPercent: number;
  discountAmount: number;
  /** Payment choices persist across sales: a cash counter stays on cash. */
  markAsPaid: boolean;
  modeOfPayment: string;
  invoiceOption: string | null;
  /** Print the invoice as soon as it is raised (when the profile names a printer). */
  autoPrint: boolean;
}

const KEY = (user: string) => `sales-app:counter:${user}`;

let seq = 0;
const uid = () => `${Date.now().toString(36)}-${(++seq).toString(36)}`;

function blankCart(): Pick<CounterState, 'customer' | 'lines' | 'orderName' | 'discountMode' | 'discountPercent' | 'discountAmount'> {
  return { customer: null, lines: [], orderName: null, discountMode: 'percent', discountPercent: 0, discountAmount: 0 };
}

/**
 * The sale being keyed in on the Counter. Unlike the phone's sale store, lines are
 * independent rows (the same item can appear twice, as the cashier typed it), and
 * the payment choices outlive the sale. Persisted per user so a refresh or a
 * browser crash never loses the cart.
 */
export const useCounterStore = defineStore('counter', {
  state: (): CounterState => ({
    user: null,
    ...blankCart(),
    markAsPaid: true,
    modeOfPayment: '',
    invoiceOption: null,
    autoPrint: true,
  }),
  getters: {
    hasLines: (s) => s.lines.length > 0,
    count: (s) => s.lines.reduce((sum, l) => sum + l.qty, 0),
    subtotal: (s) => s.lines.reduce((sum, l) => sum + l.qty * l.rate, 0),
  },
  actions: {
    hydrate(user: string | null) {
      this.user = user;
      Object.assign(this, blankCart(), { markAsPaid: true, modeOfPayment: '', invoiceOption: null, autoPrint: true });
      if (!user) return;
      try {
        const raw = localStorage.getItem(KEY(user));
        if (raw) {
          const saved = JSON.parse(raw) as Partial<CounterState>;
          Object.assign(this, saved, { user });
        }
      } catch (_e) {
        /* corrupt or unavailable storage: start clean */
      }
    },
    persist() {
      if (!this.user) return;
      try {
        const { user: _u, ...rest } = this.$state;
        localStorage.setItem(KEY(this.user), JSON.stringify(rest));
      } catch (_e) {
        /* storage full or blocked: the in-memory cart still works */
      }
    },
    /** Start the next sale. The customer stays only when the caller passes one (the profile default). */
    reset(customer: Customer | null = null) {
      Object.assign(this, blankCart(), { customer });
      this.persist();
    },
    setCustomer(customer: Customer | null) {
      if (this.customer && customer && this.customer.name !== customer.name) {
        // A different customer may price differently: keep the lines, the preview re-prices them.
        this.orderName = null;
      }
      this.customer = customer;
      this.persist();
    },
    addLine(item: CounterItem, qty: number, rate?: number): CounterLine {
      const safeQty = item.must_be_whole_number ? Math.round(qty) : qty;
      const line: CounterLine = { uid: uid(), item, qty: safeQty, rate: rate ?? item.price_list_rate ?? item.standard_rate ?? 0 };
      this.lines.push(line);
      this.persist();
      return line;
    },
    setQty(lineUid: string, qty: number) {
      const line = this.lines.find((l) => l.uid === lineUid);
      if (!line) return;
      const safe = line.item.must_be_whole_number ? Math.round(qty) : qty;
      if (safe <= 0) this.removeLine(lineUid);
      else {
        line.qty = safe;
        this.persist();
      }
    },
    setRate(lineUid: string, rate: number) {
      const line = this.lines.find((l) => l.uid === lineUid);
      if (!line) return;
      line.rate = Math.max(0, rate);
      this.persist();
    },
    removeLine(lineUid: string) {
      const idx = this.lines.findIndex((l) => l.uid === lineUid);
      if (idx > -1) this.lines.splice(idx, 1);
      this.persist();
    },
    setDiscount(mode: DiscountMode, value: number) {
      this.discountMode = mode;
      if (mode === 'percent') {
        this.discountPercent = value;
        this.discountAmount = 0;
      } else {
        this.discountAmount = value;
        this.discountPercent = 0;
      }
      this.persist();
    },
    setPayment(markAsPaid: boolean, modeOfPayment: string, invoiceOption: string | null) {
      this.markAsPaid = markAsPaid;
      this.modeOfPayment = modeOfPayment;
      this.invoiceOption = invoiceOption;
      this.persist();
    },
    setAutoPrint(value: boolean) {
      this.autoPrint = value;
      this.persist();
    },
    /** Resume a held (draft) order: its lines replace the cart and the sale updates it. */
    loadOrder(orderName: string, customer: Customer, items: SalesOrderItem[], discount?: { percent?: number; amount?: number }) {
      this.customer = customer;
      this.orderName = orderName;
      this.lines = items.map((row) => ({
        uid: uid(),
        item: {
          item_code: row.item_code,
          item_name: row.item_name,
          item_group: '',
          stock_uom: row.stock_uom || '',
          must_be_whole_number: false,
          is_stock_item: true,
          has_batch_no: false,
          has_serial_no: false,
          price_list_rate: row.price_list_rate ?? row.rate,
          standard_rate: row.rate,
          actual_qty: null,
          exact: false,
        },
        qty: row.qty,
        rate: row.rate,
      }));
      if (discount?.percent) this.setDiscount('percent', discount.percent);
      else if (discount?.amount) this.setDiscount('amount', discount.amount);
      else this.setDiscount('percent', 0);
      this.persist();
    },
  },
});
