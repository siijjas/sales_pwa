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
const loading = ref(true);

onMounted(async () => {
  if (!session.value) return;
  try {
    orders.value = await api.recentOrders(session.value.user);
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
