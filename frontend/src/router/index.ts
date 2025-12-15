import { createRouter, createWebHashHistory } from 'vue-router';
import { useSessionStore } from '../stores/session';
import DashboardView from '../views/DashboardView.vue';
import LoginView from '../views/LoginView.vue';
import CustomerSelectView from '../views/CustomerSelectView.vue';
import ItemCatalogView from '../views/ItemCatalogView.vue';
import CartView from '../views/CartView.vue';
import HistoryView from '../views/HistoryView.vue';
import OrderDetailView from '../views/OrderDetailView.vue';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/customers', name: 'customers', component: CustomerSelectView },
    { path: '/items', name: 'items', component: ItemCatalogView },
    { path: '/cart', name: 'cart', component: CartView },
    { path: '/history', name: 'history', component: HistoryView },
    { path: '/orders/:name', name: 'order-detail', component: OrderDetailView },
  ],
});

router.beforeEach(async (to, _from, next) => {
  const store = useSessionStore();
  if (store.loadingSession) {
    await store.bootstrap();
  }
  if (to.name !== 'login' && !store.session) {
    return next({ name: 'login' });
  }
  if (to.name === 'login' && store.session) {
    return next({ name: 'dashboard' });
  }
  return next();
});

export default router;
