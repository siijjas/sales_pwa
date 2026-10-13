import { defineStore } from 'pinia';
import type { Customer, CartLine, Item } from '../types';
import { lineRate } from './sale';

interface ReturnState {
  user: string | null;
  customer: Customer | null;
  lines: CartLine[];
}

const KEY = (user: string) => `sales-app:return:${user}`;

/** Items being returned for one customer (credit note). Persisted like the sale draft. */
export const useReturnStore = defineStore('returns', {
  state: (): ReturnState => ({ user: null, customer: null, lines: [] }),
  getters: {
    count: (s) => s.lines.reduce((sum, l) => sum + l.qty, 0),
    total: (s) => s.lines.reduce((sum, l) => sum + l.qty * lineRate(l), 0),
    qtyOf: (s) => (itemCode: string) => s.lines.find((l) => l.item.item_code === itemCode)?.qty || 0,
  },
  actions: {
    hydrate(user: string | null) {
      this.user = user;
      this.customer = null;
      this.lines = [];
      if (!user) return;
      try {
        const raw = localStorage.getItem(KEY(user));
        if (raw) {
          const saved = JSON.parse(raw) as Partial<ReturnState>;
          this.customer = saved.customer || null;
          this.lines = saved.lines || [];
        }
      } catch (_e) {
        /* start clean */
      }
    },
    persist() {
      if (!this.user) return;
      try {
        localStorage.setItem(KEY(this.user), JSON.stringify({ customer: this.customer, lines: this.lines }));
      } catch (_e) {
        /* ignore */
      }
    },
    start(customer: Customer) {
      if (this.customer?.name !== customer.name) this.lines = [];
      this.customer = customer;
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
      if (line) this.setQty(line.item, line.qty + delta);
    },
    clear() {
      this.customer = null;
      this.lines = [];
      this.persist();
    },
  },
});
