import { defineStore } from 'pinia';
import type { Customer, CartLine, Item, SalesOrderItem } from '../types';

export type DiscountMode = 'percent' | 'amount';

interface SaleState {
  /** Whose draft this is; the draft is persisted per user. */
  user: string | null;
  customer: Customer | null;
  lines: CartLine[];
  /** Set when editing an existing Sales Order instead of creating a new one. */
  orderName: string | null;
  /** The order being edited is already submitted (not yet invoiced): saving updates it in place. */
  orderSubmitted: boolean;
  discountMode: DiscountMode;
  discountPercent: number;
  discountAmount: number;
}

const KEY = (user: string) => `sales-app:sale:${user}`;

function blank(): Omit<SaleState, 'user'> {
  return { customer: null, lines: [], orderName: null, orderSubmitted: false, discountMode: 'percent', discountPercent: 0, discountAmount: 0 };
}

export const lineRate = (line: CartLine) => line.rate ?? line.item.price_list_rate ?? line.item.standard_rate ?? 0;

/**
 * The sale being built: customer, lines, discount and (when resuming) the draft
 * order it belongs to. Persisted to localStorage per user so a refresh, a tab
 * kill or a phone lock mid-order never loses the cart.
 */
export const useSaleStore = defineStore('sale', {
  state: (): SaleState => ({ user: null, ...blank() }),
  getters: {
    hasDraft: (s) => !!s.customer || s.lines.length > 0,
    count: (s) => s.lines.reduce((sum, l) => sum + l.qty, 0),
    subtotal: (s) => s.lines.reduce((sum, l) => sum + l.qty * lineRate(l), 0),
    qtyOf: (s) => (itemCode: string) => s.lines.find((l) => l.item.item_code === itemCode)?.qty || 0,
  },
  actions: {
    hydrate(user: string | null) {
      this.user = user;
      Object.assign(this, blank());
      if (!user) return;
      try {
        const raw = localStorage.getItem(KEY(user));
        if (raw) {
          const saved = JSON.parse(raw) as Partial<SaleState>;
          Object.assign(this, blank(), saved, { user });
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
        /* storage full or blocked: the in-memory draft still works */
      }
    },
    /** Start over. Keeps the customer when `keepCustomer` (e.g. "add another order"). */
    reset(keepCustomer = false) {
      const customer = keepCustomer ? this.customer : null;
      Object.assign(this, blank(), { customer });
      this.persist();
    },
    setCustomer(customer: Customer | null) {
      if (this.customer && customer && this.customer.name !== customer.name) {
        // A different customer means different prices: the lines no longer apply.
        this.lines = [];
        this.orderName = null;
        this.orderSubmitted = false;
      }
      this.customer = customer;
      this.persist();
    },
    /** Load an existing order (a draft, or a submitted one not yet invoiced) into the sale for editing. */
    loadOrder(
      orderName: string,
      customer: Customer,
      items: SalesOrderItem[],
      discount?: { percent?: number; amount?: number },
      submitted = false,
    ) {
      this.customer = customer;
      this.orderName = orderName;
      this.orderSubmitted = submitted;
      this.lines = items.map((line) => ({
        item: {
          item_code: line.item_code,
          item_name: line.item_name,
          description: '',
          stock_uom: line.stock_uom || '',
          item_group: '',
          price_list_rate: line.rate,
          standard_rate: line.rate,
        },
        qty: line.qty,
        rate: line.rate,
      }));
      if (discount?.percent) {
        this.discountMode = 'percent';
        this.discountPercent = discount.percent;
        this.discountAmount = 0;
      } else if (discount?.amount) {
        this.discountMode = 'amount';
        this.discountAmount = discount.amount;
        this.discountPercent = 0;
      } else {
        this.discountMode = 'percent';
        this.discountPercent = 0;
        this.discountAmount = 0;
      }
      this.persist();
    },
    setQty(item: Item, qty: number) {
      const idx = this.lines.findIndex((l) => l.item.item_code === item.item_code);
      const safe = item.must_be_whole_number ? Math.round(qty) : qty;
      if (safe <= 0) {
        if (idx > -1) this.lines.splice(idx, 1);
      } else if (idx > -1) {
        this.lines[idx].qty = safe;
      } else {
        this.lines.push({ item, qty: safe, rate: item.price_list_rate ?? item.standard_rate });
      }
      this.persist();
    },
    changeQty(itemCode: string, delta: number) {
      const line = this.lines.find((l) => l.item.item_code === itemCode);
      if (!line) return;
      this.setQty(line.item, line.qty + delta);
    },
    setRate(itemCode: string, rate: number) {
      const line = this.lines.find((l) => l.item.item_code === itemCode);
      if (line) {
        line.rate = rate;
        this.persist();
      }
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
  },
});
