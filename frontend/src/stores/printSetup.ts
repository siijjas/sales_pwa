import { defineStore } from 'pinia';

/** Where a document goes: '' = what the profile says, 'pdf' = open the PDF, else a Sales Printer name. */
export const PDF = 'pdf';

export interface PrintPreference {
  /** A print format name; '' = the profile's (or the doctype's default). */
  format: string;
  printer: string;
}

interface PrintSetupState {
  user: string | null;
  prefs: Record<string, PrintPreference>;
  /** The setup sheet, when open: which doctype, and a document to print once chosen. */
  sheet: { doctype: string; name?: string; isReturn?: boolean } | null;
}

const KEY = (user: string) => `sales-app:print:${user}`;
const BLANK: PrintPreference = { format: '', printer: '' };

/**
 * Each person's own print choices, per document type: which format, and whether it
 * goes to a printer or opens as a PDF. The Sales Profile sets the defaults for
 * everyone on it; this is the cashier's own override, kept in this browser, so a
 * counter PC stays on its receipt printer and a manager's laptop stays on PDF.
 */
export const usePrintSetupStore = defineStore('printSetup', {
  state: (): PrintSetupState => ({ user: null, prefs: {}, sheet: null }),
  getters: {
    prefFor: (s) => (doctype: string): PrintPreference => s.prefs[doctype] || BLANK,
  },
  actions: {
    hydrate(user: string | null) {
      this.user = user;
      this.prefs = {};
      this.sheet = null;
      if (!user) return;
      try {
        const raw = localStorage.getItem(KEY(user));
        if (raw) this.prefs = JSON.parse(raw) as Record<string, PrintPreference>;
      } catch (_e) {
        /* corrupt or unavailable storage: the profile's defaults apply */
      }
    },
    set(doctype: string, pref: Partial<PrintPreference>) {
      this.prefs = { ...this.prefs, [doctype]: { ...this.prefFor(doctype), ...pref } };
      if (!this.user) return;
      try {
        localStorage.setItem(KEY(this.user), JSON.stringify(this.prefs));
      } catch (_e) {
        /* storage blocked: the choice still holds for this visit */
      }
    },
    /** Open the setup sheet for a doctype; with `name`, the sheet offers to print that document at once. */
    open(doctype: string, opts: { name?: string; isReturn?: boolean } = {}) {
      this.sheet = { doctype, ...opts };
    },
    close() {
      this.sheet = null;
    },
  },
});
