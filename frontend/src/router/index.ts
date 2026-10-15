import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';
import { useSessionStore } from '../stores/session';
import HomeView from '../views/HomeView.vue';
import LoginView from '../views/LoginView.vue';

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean;
    /** Hide the phone tab bar (flows own the bottom edge). */
    tabs?: boolean;
    requiresManager?: boolean;
    requiresDriverConfig?: boolean;
    capability?: string;
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', name: 'home', component: HomeView },

  // ── Selling: one flow, three steps ──────────────────────────────────────
  { path: '/sell', name: 'sell', redirect: { name: 'sell-customer' } },
  { path: '/sell/customer', name: 'sell-customer', component: () => import('../views/sale/SaleCustomerView.vue'), meta: { tabs: false } },
  { path: '/sell/items', name: 'sell-items', component: () => import('../views/sale/SaleItemsView.vue'), meta: { tabs: false } },
  { path: '/sell/review', name: 'sell-review', component: () => import('../views/sale/SaleReviewView.vue'), meta: { tabs: false } },

  // ── Counter: fast keyboard order entry on a PC ──────────────────────────
  { path: '/counter', name: 'counter', component: () => import('../views/CounterView.vue'), meta: { capability: 'can_counter_sell' } },
  { path: '/counter/purchase', name: 'counter-purchase', component: () => import('../views/CounterPurchaseView.vue'), meta: { capability: 'can_counter_purchase' } },

  // ── Customers ───────────────────────────────────────────────────────────
  { path: '/customers', name: 'customers', component: () => import('../views/CustomersView.vue') },
  { path: '/customers/:name', name: 'customer', component: () => import('../views/CustomerView.vue') },
  { path: '/customers/:name/collect', name: 'collect', component: () => import('../views/CollectPaymentView.vue'), meta: { tabs: false } },
  { path: '/customers/:name/ledger', name: 'ledger', component: () => import('../views/CustomerLedgerView.vue'), meta: { capability: 'shows_customer_balance' } },
  { path: '/customers/:name/return', name: 'return-items', component: () => import('../views/ReturnItemsView.vue'), meta: { capability: 'can_return', tabs: false } },
  { path: '/customers/:name/return/review', name: 'return-review', component: () => import('../views/ReturnReviewView.vue'), meta: { capability: 'can_return', tabs: false } },

  // ── Activity and documents ──────────────────────────────────────────────
  { path: '/activity', name: 'activity', component: () => import('../views/ActivityView.vue') },
  { path: '/orders/:name', name: 'order', component: () => import('../views/OrderView.vue') },
  { path: '/payments/:name', name: 'payment', component: () => import('../views/PaymentView.vue') },

  // ── Stock ───────────────────────────────────────────────────────────────
  { path: '/stock', name: 'stock', component: () => import('../views/StockView.vue'), meta: { requiresDriverConfig: true, capability: 'can_view_stock' } },
  { path: '/stock/load', name: 'stock-load', component: () => import('../views/StockLoadView.vue'), meta: { requiresDriverConfig: true, capability: 'can_load_stock', tabs: false } },

  // ── Shift ───────────────────────────────────────────────────────────────
  { path: '/shift', name: 'shift', component: () => import('../views/ShiftView.vue'), meta: { capability: 'uses_shifts' } },
  { path: '/shift/open', name: 'shift-open', component: () => import('../views/ShiftOpenView.vue'), meta: { capability: 'uses_shifts', tabs: false } },
  { path: '/shift/close', name: 'shift-close', component: () => import('../views/ShiftCloseView.vue'), meta: { capability: 'uses_shifts', tabs: false } },
  { path: '/shift/cash', name: 'shift-cash', component: () => import('../views/CashMovementView.vue'), meta: { capability: 'uses_shifts' } },
  { path: '/shift/reports', name: 'shift-reports', component: () => import('../views/ShiftReportsView.vue') },
  { path: '/shift/summary', name: 'shift-summary', component: () => import('../views/ShiftReportView.vue') },
  { path: '/shift/closing-report/:name', name: 'closing-report', component: () => import('../views/ShiftReportView.vue') },

  // ── Manager ─────────────────────────────────────────────────────────────
  { path: '/fleet/:kind', name: 'fleet-entries', component: () => import('../views/FleetEntriesView.vue'), meta: { requiresManager: true } },
  { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue'), meta: { requiresManager: true } },
  { path: '/staff', name: 'staff', component: () => import('../views/StaffView.vue'), meta: { requiresManager: true } },
  { path: '/setup', name: 'setup', component: () => import('../views/SetupView.vue'), meta: { requiresManager: true } },
  { path: '/setup/invoice-options', name: 'invoice-options', component: () => import('../views/InvoiceOptionsView.vue'), meta: { requiresManager: true } },

  { path: '/more', name: 'more', component: () => import('../views/MoreView.vue') },

  // ── Old links (bookmarks, printed QR codes, notifications) ──────────────
  { path: '/history', redirect: { name: 'activity' } },
  { path: '/daily-log/:type', redirect: (to) => ({ name: 'activity', query: { tab: to.params.type === 'payments' ? 'payments' : 'orders' } }) },
  { path: '/orders/:name/detail', redirect: (to) => ({ name: 'order', params: { name: to.params.name } }) },
  { path: '/payment-detail/:name', redirect: (to) => ({ name: 'payment', params: { name: to.params.name } }) },
  { path: '/items', redirect: { name: 'sell-items' } },
  { path: '/cart', redirect: { name: 'sell-review' } },
  { path: '/payment', redirect: { name: 'customers' } },
  { path: '/ledger', redirect: { name: 'customers' } },
  { path: '/return-items', redirect: { name: 'customers' } },
  { path: '/return-cart', redirect: { name: 'customers' } },
  { path: '/stock-dashboard', redirect: { name: 'stock' } },
  { path: '/transfer', redirect: { name: 'stock-load' } },
  { path: '/expenses', redirect: { name: 'shift-cash' } },
  { path: '/eod', redirect: { name: 'shift-close' } },
  { path: '/shift/report/x', redirect: (to) => ({ name: 'shift-summary', query: to.query }) },
  { path: '/shift/report/y/:name', redirect: (to) => ({ name: 'closing-report', params: { name: to.params.name } }) },
  { path: '/sales-profiles', redirect: { name: 'staff' } },
  { path: '/driver-setup', redirect: { name: 'staff' } },
  { path: '/settings', redirect: { name: 'setup' } },
  { path: '/invoice-options', redirect: { name: 'invoice-options' } },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(_to, _from, saved) {
    return saved || { top: 0 };
  },
});

router.beforeEach(async (to, _from, next) => {
  const store = useSessionStore();
  if (store.loadingSession) {
    await store.bootstrap();
  }
  if (!to.meta.public && !store.session) {
    return next({ name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} });
  }
  if (to.name === 'login' && store.session) {
    return next({ name: 'home' });
  }
  if (to.meta.requiresDriverConfig && !store.driverConfig && !store.isManager) {
    return next({ name: 'home', query: { setup: 'driver-profile' } });
  }
  // Profile-type gating (Field Sales has no van stock, returns or, by default, shifts).
  // Managers keep every screen: they close other people's shifts and inspect any van.
  const capability = to.meta.capability as keyof typeof store.capabilities | undefined;
  if (capability && store.driverConfig && !store.capabilities[capability] && !store.isManager) {
    return next({ name: 'home' });
  }
  if (to.meta.requiresManager && !store.isManager) {
    return next({ name: 'home' });
  }
  return next();
});

export default router;
