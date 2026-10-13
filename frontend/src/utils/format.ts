// Shared number/date formatting. Every screen reads money and quantities through
// these so the whole app agrees on decimals, separators and date styles.

export function money(n: number | null | undefined, decimals = 2): string {
  return (Number(n) || 0).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** Signed money: "+1,200.00" / "−340.00" / "0.00". */
export function signedMoney(n: number | null | undefined): string {
  const v = Number(n) || 0;
  if (!v) return money(0);
  return `${v > 0 ? '+' : '−'}${money(Math.abs(v))}`;
}

export function qty(n: number | null | undefined): string {
  return (Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

export function pct(n: number | null | undefined, decimals = 1): string {
  return `${(Number(n) || 0).toFixed(decimals)}%`;
}

function parse(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  if (value instanceof Date) return value;
  // Frappe sends "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS(.ffffff)"; both parse as local time.
  const iso = value.length === 10 ? `${value}T00:00:00` : value.replace(' ', 'T').split('.')[0];
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "13 Oct" or "13 Oct 2025" when the year differs from today. */
export function shortDate(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return '';
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: sameYear ? undefined : 'numeric' });
}

/** "Mon, 13 Oct 2025". */
export function longDate(value: string | Date | null | undefined): string {
  const d = parse(value);
  return d ? d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : '';
}

/** "Today", "Yesterday" or a short date. */
export function relativeDate(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return '';
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return shortDate(d);
}

/** "09:41". */
export function time(value: string | Date | null | undefined): string {
  const d = parse(value);
  return d ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '';
}

/** "Today 09:41" / "13 Oct 09:41". */
export function dateTime(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return '';
  return `${relativeDate(d)} ${time(d)}`;
}

/** Today's date as the ISO day Frappe expects. */
export function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function initials(name: string | null | undefined): string {
  return (name || '?')
    .split(' ')
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function plural(n: number, singular: string, pluralForm?: string): string {
  return `${n} ${n === 1 ? singular : pluralForm || `${singular}s`}`;
}
