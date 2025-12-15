<template>
  <div class="min-h-full bg-gray-50">
    <div class="px-4 py-3 bg-white border-b flex items-center justify-between gap-2 sticky top-0">
      <div class="flex items-center gap-3">
        <button class="text-sm text-gray-600" @click="$router.push({ name: 'dashboard' })">Dashboard</button>
        <button class="text-sm text-blue-600 font-semibold" @click="$router.push({ name: 'customers' })">
          New Order
        </button>
      </div>
      <div class="flex items-center gap-3">
        <h2 class="text-base font-semibold text-gray-900">Order History</h2>
        <button class="text-sm text-blue-600" @click="reload">Refresh</button>
        <button class="text-sm text-gray-600" @click="logout">Logout</button>
      </div>
    </div>
    <div class="p-4 space-y-3">
      <div v-if="loading" class="space-y-2">
        <div class="h-20 bg-white rounded-xl shadow-sm animate-pulse" />
        <div class="h-20 bg-white rounded-xl shadow-sm animate-pulse" />
      </div>
      <div v-else-if="orders.length === 0" class="bg-white rounded-xl p-4 shadow-sm text-sm text-gray-500">
        No orders found.
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="order in orders"
          :key="order.name"
          class="bg-white rounded-xl shadow-sm border p-4 cursor-pointer"
          role="button"
          @click="openOrder(order.name)"
        >
          <div class="flex justify-between items-center">
            <div>
              <p class="font-semibold text-gray-900">{{ order.customer_name }}</p>
              <p class="text-xs text-gray-500">{{ order.name }} • {{ order.transaction_date }}</p>
            </div>
            <span class="text-[11px] font-bold px-2 py-1 rounded-full bg-gray-100 text-gray-800 uppercase">{{ order.status }}</span>
          </div>
          <p class="mt-2 font-semibold text-gray-900">
            {{ currency }} {{ order.grand_total?.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import type { SalesOrder } from '../types';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';

const store = useSessionStore();
const router = useRouter();
const session = computed(() => store.session);
const currency = computed(() => store.currencyDisplay);
const orders = ref<SalesOrder[]>([]);
const loading = ref(true);

const load = async () => {
  if (!session.value) return;
  loading.value = true;
  orders.value = await api.recentOrders(session.value.user);
  loading.value = false;
};

const reload = () => load();

onMounted(load);

const openOrder = (name: string) => {
  router.push({ name: 'order-detail', params: { name } });
};

const logout = async () => {
  await store.logout();
  router.push({ name: 'login' });
};
</script>
