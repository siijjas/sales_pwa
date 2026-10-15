import { defineStore } from 'pinia';
import type { CounterItem, CounterLine, Customer, PurchaseOrderDetail } from '../types';

/** The supplier in the Customer shape the Counter's party box takes. */
export type SupplierPick = Customer;

interface PurchaseState {
  /** Whose cart this is; the cart is persisted per user. */
  user: string | null;
  supplier: SupplierPick | null;
  lines: CounterLine[];
  /** Set when a held (draft) Purchase Order was resumed: submitting updates it. */
  orderName: string | null;
  /** Payment choices persist across purchases, like the sale side's. */
  markAsPaid: boolean;
  modeOfPayment: string;
}

const KEY = (user: string) => `sales-app:counter-purchase:${user}`;

let seq = 0;
const uid = () => `${Date.now().toString(36)}-p${(++seq).toString(36)}`;

function blankCart(): Pick<PurchaseState, 'supplier' | 'lines' | 'orderName'> {
  return { supplier: null, lines: [], orderName: null };
}

/**
 * The Purchase Order being keyed in on the Counter's Purchase screen: the mirror
 * of stores/counter for buying. Rates are always the cashier's to change (they key
 * in what the supplier charged). Persisted per user, apart from the sale cart, so
 * switching between the two screens loses neither.
 */
export const useCounterPurchaseStore = defineStore('counterPurchase', {
  state: (): PurchaseState => ({ user: null, ...blankCart(), markAsPaid: true, modeOfPayment: '' }),
  getters: {
    hasLines: (s) => s.lines.length > 0,
    count: (s) => s.lines.reduce((sum, l) => sum + l.qty, 0),
    subtotal: (s) => s.lines.reduce((sum, l) => sum + l.qty * l.rate, 0),
  },
  actions: {
    hydrate(user: string | null) {
      this.user = user;
      Object.assign(this, blankCart(), { markAsPaid: true, modeOfPayment: '' });
      if (!user) return;
      try {
        const raw = localStorage.getItem(KEY(user));
        if (raw) Object.assign(this, JSON.parse(raw) as Partial<PurchaseState>, { user });
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
    reset() {
      Object.assign(this, blankCart());
      this.persist();
    },
    setSupplier(supplier: SupplierPick | null) {
      this.supplier = supplier;
      this.persist();
    },
    addLine(item: CounterItem, qty: number, rate?: number): CounterLine {
      const safeQty = item.must_be_whole_number ? Math.round(qty) : qty;
      const line: CounterLine = { uid: uid(), item, qty: safeQty, rate: rate ?? item.price_list_rate ?? 0 };
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
    setPayment(markAsPaid: boolean, modeOfPayment: string) {
      this.markAsPaid = markAsPaid;
      this.modeOfPayment = modeOfPayment;
      this.persist();
    },
    /** Resume a held (draft) Purchase Order: its lines replace the cart. */
    loadOrder(order: PurchaseOrderDetail) {
      this.supplier = { name: order.supplier, customer_name: order.supplier_name || order.supplier, customer_group: '', territory: '' };
      this.orderName = order.order;
      this.lines = order.items.map((row) => ({
        uid: uid(),
        item: {
          item_code: row.item_code,
          item_name: row.item_name,
          item_group: '',
          stock_uom: row.stock_uom || row.uom || '',
          must_be_whole_number: false,
          is_stock_item: true,
          has_batch_no: false,
          has_serial_no: false,
          price_list_rate: row.rate,
          standard_rate: row.rate,
          actual_qty: null,
          exact: false,
        },
        qty: row.qty,
        rate: row.rate,
      }));
      this.persist();
    },
  },
});
