import { useSessionStore } from '../stores/session';
import { PDF, usePrintSetupStore } from '../stores/printSetup';
import { useToast } from '../composables/useToast';
import * as api from '../api/frappe';

// Tap Print → the print sheet (PrintSetupSheet) asks for the format and the printer,
// or the PDF, every time; it opens on what this person picked last for the document
// type, else on what their profile names. A printer job is rendered on the server and
// queued for the printer's agent (sales_pwa.sales_app.printing). The PDF stays one tap
// away in every toast, because a printer out of paper must never leave the customer
// without a copy.

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
  /** The format the screen suggests (the shift reports); the person can still pick another. */
  format?: string;
  /** A credit note suggests the credit-note printer first, then the invoice one. */
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

  /** Ask how to print `name`: opens the print sheet, which prints once the person confirms. */
  const print = (doctype: string, name: string, opts: PrintOptions = {}) => setup.open({ doctype, name, ...opts });

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

  /**
   * Print `name` with the format and printer the sheet confirmed. Call it inside the
   * click or keypress: the PDF opens in a new tab, and a popup opened after an await
   * is blocked on phones.
   */
  async function send(doctype: string, name: string, format: string, printer: string, isReturn = false) {
    const openPdf = () => api.downloadPdf(doctype, name, format || undefined);
    if (!printer || printer === PDF) {
      openPdf();
      return;
    }
    const again = () => print(doctype, name, { format, isReturn });
    const pending = toast.info(`Sending to ${printer}…`, { duration: 15000 });
    let receipt;
    try {
      receipt = await api.printDocument(doctype, name, format || undefined, printer);
    } catch (e) {
      toast.dismiss(pending);
      toast.error('Could not print', { message: (e as Error).message, action: { label: 'Print again', run: again }, duration: 10000 });
      return;
    }
    toast.dismiss(pending);
    if (!receipt.job) {
      toast.error('Could not print', { message: `${printer} took no job.`, action: { label: 'Open PDF', run: openPdf }, duration: 10000 });
      return;
    }
    const where = receipt.printer || printer;
    if (receipt.online === false) {
      toast.warning(`Queued for ${where}`, { message: 'Its print agent is offline; it prints when the agent reconnects.', action: { label: 'Open PDF', run: openPdf }, duration: 8000 });
    } else {
      toast.success(`Sent to ${where}`, { action: { label: 'Open PDF', run: openPdf }, duration: 5000 });
    }
    void watch(receipt.job, where, openPdf);
  }

  return { print, send, profilePrinterFor };
}
