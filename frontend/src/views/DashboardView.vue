<template>
  <div class="min-h-full bg-gray-50">
    <div class="px-4 py-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <p class="text-xs text-gray-500">Welcome</p>
          <h2 class="text-lg font-semibold text-gray-900">{{ session?.full_name }}</h2>
        </div>
        <div class="flex items-center gap-2">
          <button class="bg-gray-100 text-gray-800 text-sm px-3 py-2 rounded-lg" @click="logout">
            Logout
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-6">
        <button 
          class="bg-blue-600 text-white text-sm px-3 py-3 rounded-xl font-semibold shadow-sm flex flex-col items-center justify-center gap-1" 
          @click="$router.push({ name: 'customers', query: { redirect: 'order' } })"
        >
          <span>+ New Order</span>
        </button>
        <button 
          class="bg-emerald-600 text-white text-sm px-3 py-3 rounded-xl font-semibold shadow-sm flex flex-col items-center justify-center gap-1" 
          @click="$router.push({ name: 'customers', query: { redirect: 'payment' } })"
        >
          <span>+ New Payment</span>
        </button>
        <button 
          class="bg-white border border-gray-200 text-gray-700 text-sm px-3 py-3 rounded-xl font-semibold shadow-sm flex flex-col items-center justify-center gap-1" 
          @click="$router.push({ name: 'ledger' })"
        >
          <span>Customer Ledger</span>
        </button>

      </div>

      <div class="mb-6">
        <p class="text-xs font-semibold text-gray-600 uppercase mb-3">Today's Overview</p>
        <div class="grid grid-cols-2 gap-3">
          <div 
            class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 active:scale-[0.98] transition-transform cursor-pointer"
            @click="$router.push({ name: 'daily-log', params: { type: 'orders' } })"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="p-1.5 bg-blue-50 text-blue-600 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
              </span>
              <p class="text-xs text-gray-500 font-medium">Orders</p>
            </div>
            <div class="mt-2">
              <p class="text-lg font-bold text-gray-900">{{ dailySummary?.sales_orders.count || 0 }}</p>
              <p class="text-xs text-gray-400 font-medium">{{ currency }} {{ (dailySummary?.sales_orders.total || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
            </div>
          </div>
          <div 
            class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 active:scale-[0.98] transition-transform cursor-pointer"
            @click="$router.push({ name: 'daily-log', params: { type: 'payments' } })"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="p-1.5 bg-emerald-50 text-emerald-600 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>
              </span>
              <p class="text-xs text-gray-500 font-medium">Payments</p>
            </div>
            <div class="mt-2">
              <p class="text-lg font-bold text-gray-900">{{ dailySummary?.payments.count || 0 }}</p>
              <p class="text-xs text-gray-400 font-medium">{{ currency }} {{ (dailySummary?.payments.total || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="mb-4">
        <p class="text-xs font-semibold text-gray-600 uppercase">Recent Orders</p>
      </div>

      <div v-if="loading" class="space-y-3">
        <div class="h-20 bg-white rounded-xl shadow-sm animate-pulse" />
        <div class="h-20 bg-white rounded-xl shadow-sm animate-pulse" />
      </div>
      <div v-else-if="orders.length === 0" class="text-sm text-gray-500 bg-white rounded-xl p-4 shadow-sm">
        No orders yet. Create one to get started.
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="order in orders"
          :key="order.name"
          class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 cursor-pointer"
          role="button"
          @click="openOrder(order.name)"
        >
          <div class="flex justify-between items-center">
            <div>
              <p class="font-semibold text-gray-900">{{ order.customer_name }}</p>
              <p class="text-xs text-gray-500">{{ order.name }} • {{ order.transaction_date }}</p>
            </div>
            <span class="text-xs font-bold bg-gray-100 text-gray-800 px-2 py-1 rounded-full uppercase">{{ order.status }}</span>
          </div>
          <div class="mt-2 text-sm font-semibold text-gray-900">
            {{ currency }} {{ order.grand_total?.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import * as api from '../api/frappe';
import type { SalesOrder } from '../types';

const store = useSessionStore();
const router = useRouter();
const session = computed(() => store.session);
const currency = computed(() => store.currencyDisplay);
const orders = ref<SalesOrder[]>([]);
const dailySummary = ref<{ sales_orders: { count: number; total: number }; payments: { count: number; total: number } } | null>(null);
const loading = ref(true);

onMounted(async () => {
  if (!session.value) return;
  try {
    const [ordersData, summaryData] = await Promise.all([
      api.recentOrders(session.value.user),
      api.getDailySummary()
    ]);
    orders.value = ordersData;
    dailySummary.value = summaryData;
  } finally {
    loading.value = false;
  }
});

const openOrder = (name: string) => {
  router.push({ name: 'order-detail', params: { name } });
};

const logout = async () => {
  await store.logout();
  router.push({ name: 'login' });
};
</script>
