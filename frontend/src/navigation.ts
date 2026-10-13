import { useSessionStore } from './stores/session';

export interface NavItem {
  name: string;
  label: string;
  icon: string;
  to: { name: string };
  /** Route names that light this item up. */
  names: string[];
  hint?: string;
}

/**
 * One place that decides what each person can reach. The shell renders the first
 * five as tabs (phone) or the rail (tablet/desktop); the More page lists the rest.
 */
export function useNavigation() {
  const store = useSessionStore();
  const caps = store.capabilities;
  const manager = store.isManager;
  const hasProfile = !!store.driverConfig;

  const home: NavItem = manager && !hasProfile
    ? { name: 'home', label: 'Fleet', icon: 'activity', to: { name: 'home' }, names: ['home'] }
    : { name: 'home', label: 'Home', icon: 'home', to: { name: 'home' }, names: ['home'] };

  const sell: NavItem = { name: 'sell', label: 'Sell', icon: 'cart', to: { name: 'sell' }, names: ['sell', 'sell-customer', 'sell-items', 'sell-review'], hint: 'New order, invoice and collect' };
  const customers: NavItem = { name: 'customers', label: 'Customers', icon: 'users', to: { name: 'customers' }, names: ['customers', 'customer', 'collect', 'ledger', 'return-items', 'return-review'], hint: 'Balances, payments, returns' };
  const activity: NavItem = { name: 'activity', label: 'Activity', icon: 'receipt', to: { name: 'activity' }, names: ['activity', 'order', 'payment'], hint: 'Orders and payments' };
  const stock: NavItem = { name: 'stock', label: 'Stock', icon: 'boxes', to: { name: 'stock' }, names: ['stock', 'stock-load'], hint: 'Van stock and loading' };
  const shift: NavItem = { name: 'shift', label: 'Shift', icon: 'clock', to: { name: 'shift' }, names: ['shift', 'shift-open', 'shift-close', 'shift-cash', 'shift-reports', 'shift-summary', 'closing-report'], hint: 'Open, cash out, close, reports' };
  const reports: NavItem = { name: 'reports', label: 'Reports', icon: 'list', to: { name: 'reports' }, names: ['reports'], hint: 'Sales, cash and stock across staff' };
  const staff: NavItem = { name: 'staff', label: 'Staff', icon: 'user', to: { name: 'staff' }, names: ['staff'], hint: 'Sales profiles and assignments' };
  const setup: NavItem = { name: 'setup', label: 'Setup', icon: 'settings', to: { name: 'setup' }, names: ['setup', 'invoice-options'], hint: 'Invoice options and app settings' };
  const more: NavItem = { name: 'more', label: 'More', icon: 'list', to: { name: 'more' }, names: ['more'] };

  const canStock = hasProfile ? caps.can_view_stock : manager;
  const canShift = manager || caps.uses_shifts;

  const primary: NavItem[] = [home, sell, customers];
  if (manager && !hasProfile) primary.push(reports);
  else if (canStock) primary.push(stock);
  else primary.push(activity);
  primary.push(more);

  const inPrimary = new Set(primary.map((i) => i.name));
  const work: NavItem[] = [activity, stock, shift].filter((i) => !inPrimary.has(i.name) && (i.name !== 'stock' || canStock) && (i.name !== 'shift' || canShift));
  const manage: NavItem[] = manager ? [reports, staff, setup].filter((i) => !inPrimary.has(i.name)) : [];

  return { primary, work, manage };
}
