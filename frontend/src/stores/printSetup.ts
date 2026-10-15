import { defineStore } from 'pinia';

/** Where a document goes: 'pdf' = open the PDF, else a Sales Printer name. */
export const PDF = 'pdf';

export interface PrintPreference {
  /** A print format name; '' = none picked yet. */
  format: string;
  /** A Sales Printer name, 'pdf', or '' = none picked yet. */
  printer: string;
}

/** A Print tap waiting in the sheet: the document, and the format its screen suggests (the shift reports). */
export interface PrintRequest {
  doctype: string;
  name: string;
  isReturn?: boolean;
  format?: string;
}

interface PrintSetupState {
  user: string | null;
  prefs: Record<string, PrintPreference>;
  sheet: PrintRequest | null;
}

const KEY = (user: string) => `sales-app:print:${user}`;
const BLANK: PrintPreference = { format: '', printer: '' };

/**
 * Every Print tap opens the print sheet (PrintSetupSheet), where the person picks the
 * format and the printer (or the PDF) for that one print. What they picked last, per
 * document type, is kept in this browser only so the sheet opens on it: a counter PC
 * comes back to its receipt printer, a laptop to the PDF, and Enter prints.
 */
export const usePrintSetupStore = defineStore('printSetup', {
  state: (): PrintSetupState => ({ user: null, prefs: {}, sheet: null }),
  getters: {
    lastFor: (s) => (doctype: string): PrintPreference => s.prefs[doctype] || BLANK,
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
        /* corrupt or unavailable storage: the sheet opens on the profile's defaults */
      }
    },
    remember(doctype: string, pref: PrintPreference) {
      this.prefs = { ...this.prefs, [doctype]: { ...pref } };
      if (!this.user) return;
      try {
        localStorage.setItem(KEY(this.user), JSON.stringify(this.prefs));
      } catch (_e) {
        /* storage blocked: the choice still holds for this visit */
      }
    },
    open(request: PrintRequest) {
      this.sheet = { ...request };
    },
    close() {
      this.sheet = null;
    },
  },
});
