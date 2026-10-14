import { useSessionStore } from '../stores/session';
import { PDF, usePrintSetupStore } from '../stores/printSetup';
import { useToast } from '../composables/useToast';
import * as api from '../api/frappe';

// Tap Print → paper. The person's own print setup (stores/printSetup: a format, and a
// printer or the PDF) comes first; otherwise the profile decides: when it names a
// Sales Printer for the document, the server renders it and queues it for the
// printer's agent (sales_pwa.sales_app.printing), else the PDF opens. The PDF stays
// one tap away in every toast, because a printer out of paper must never leave the
// customer without a copy.

const PRINTER_FIELD: Record<string, 'order_printer' | 'invoice_printer' | 'payment_printer' | 'shift_report_printer'> = {
  'Sales Order': 'order_printer',
  'Sales Invoice': 'invoice_printer',
  'Payment Entry': 'payment_printer',
  'Sales Shift Opening': 'shift_report_printer',
  'Sales Shift Closing': 'shift_report_printer',
};

const POLL_MS = 1500;
const POLL_FOR_MS = 25000;

export interface PrintOptions {
  /** A print format named by the caller (the shift reports); blank = the person's choice, then the profile's. */
  format?: string;
  /** A credit note takes the credit-note printer first, then the invoice one. */
  isReturn?: boolean;
}

export function usePrint() {
  const session = useSessionStore();
  const setup = usePrintSetupStore();
  const toast = useToast();

  /** The printer the signed-in person's own profile names for this document, if any. */
  const profilePrinterFor = (doctype: string, isReturn = false): string | null => {
    const config = session.driverConfig;
    if (!config) return null;
    if (isReturn && config.return_printer) return config.return_printer;
    const field = PRINTER_FIELD[doctype];
    return (field && config[field]) || null;
  };

  /** Where Print sends this document: a printer name, 'pdf', or null when only the server knows (a manager without a profile). */
  const printerFor = (doctype: string, isReturn = false): string | null => {
    const chosen = setup.prefFor(doctype).printer;
    if (chosen) return chosen;
    const profile = profilePrinterFor(doctype, isReturn);
    if (profile) return profile;
    return session.isManager && !session.driverConfig ? null : PDF;
  };

  /**
   * Whether Print goes to a printer rather than opening the PDF. A manager without a
   * profile and no choice of their own prints the way the document owner's profile
   * would, which only the server knows, so they go through the server too.
   */
  const printsDirectly = (doctype: string, isReturn = false) => printerFor(doctype, isReturn) !== PDF;

  /** Open the print setup sheet for a doctype; with `name`, it prints that document once chosen. */
  const choose = (doctype: string, opts: { name?: string; isReturn?: boolean } = {}) => setup.open(doctype, opts);

  async function watch(job: string, printer: string, openPdf: () => void) {
    const until = Date.now() + POLL_FOR_MS;
    while (Date.now() < until) {
      await new Promise((r) => window.setTimeout(r, POLL_MS));
      let status;
      try {
        status = await api.getPrintJobStatus(job);
      } catch (_e) {
        return;
      }
      if (status.status === 'Printed') {
        toast.success(`Printed on ${printer}`);
        return;
      }
      if (status.status === 'Failed') {
        toast.error(`${printer} did not print`, { message: status.error, action: { label: 'Open PDF', run: openPdf }, duration: 10000 });
        return;
      }
    }
    toast.warning(`${printer} has not confirmed yet`, { message: 'The job stays queued; the agent prints it when it reconnects.', action: { label: 'Open PDF', run: openPdf }, duration: 8000 });
  }

  /** Print `name` the way the person's setup, then the profile, says: a printer, or the PDF in a new tab. */
  async function print(doctype: string, name: string, opts: PrintOptions = {}) {
    const format = opts.format || setup.prefFor(doctype).format || undefined;
    const openPdf = () => api.downloadPdf(doctype, name, format);
    const target = printerFor(doctype, opts.isReturn);
    if (target === PDF) {
      // Synchronous, inside the tap: a popup opened after an await is blocked on phones.
      openPdf();
      return;
    }
    const chosen = setup.prefFor(doctype).printer;
    const pending = toast.info('Sending to the printer…', { duration: 15000 });
    let receipt;
    try {
      receipt = await api.printDocument(doctype, name, format, chosen || undefined);
    } catch (e) {
      toast.dismiss(pending);
      toast.error('Could not print', {
        message: (e as Error).message,
        action: chosen ? { label: 'Choose printer', run: () => choose(doctype, { name, isReturn: opts.isReturn }) } : { label: 'Open PDF', run: openPdf },
        duration: 10000,
      });
      return;
    }
    toast.dismiss(pending);
    if (!receipt.job) {
      // No printer for this document after all (a manager without a profile): pick one, or the PDF.
      toast.info('No printer set for this document', {
        message: 'Choose a printer and format for yourself, or open the PDF.',
        action: { label: 'Choose printer', run: () => choose(doctype, { name, isReturn: opts.isReturn }) },
        duration: 10000,
      });
      return;
    }
    const printer = receipt.printer || 'the printer';
    if (receipt.online === false) {
      toast.warning(`Queued for ${printer}`, { message: 'Its print agent is offline; it prints when the agent reconnects.', action: { label: 'Open PDF', run: openPdf }, duration: 8000 });
    } else {
      toast.success(`Sent to ${printer}`, { action: { label: 'Open PDF', run: openPdf }, duration: 5000 });
    }
    void watch(receipt.job, printer, openPdf);
  }

  return { print, printerFor, printsDirectly, choose };
}
