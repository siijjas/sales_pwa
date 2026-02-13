<template>
  <div class="flex flex-col h-full bg-white">
    <div class="px-4 py-3 border-b border-gray-100 sticky top-0 bg-white flex items-center gap-2">
      <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
      <input
        v-model="txt"
        class="flex-1 bg-gray-100 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
        placeholder="Search customers"
      />
    </div>
    <div class="flex-1 overflow-y-auto px-4">
      <div v-if="loading" class="space-y-2 py-3">
        <div class="h-14 bg-gray-100 rounded-lg animate-pulse"></div>
        <div class="h-14 bg-gray-100 rounded-lg animate-pulse"></div>
      </div>
      <div v-else class="divide-y divide-gray-100">
        <button
          v-for="customer in customers"
          :key="customer.name"
          class="w-full text-left py-3 flex justify-between items-center"
          @click="selectCustomer(customer)"
        >
          <div>
            <p class="font-medium text-gray-900">{{ customer.customer_name }}</p>
            <p class="text-xs text-gray-500">{{ customer.name }}</p>
          </div>
          <span class="text-xs bg-gray-100 px-2 py-1 rounded">{{ customer.territory }}</span>
        </button>
        <p v-if="!customers.length" class="text-sm text-gray-500 py-6 text-center">No customers found</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import * as api from '../api/frappe';
import type { Customer } from '../types';
import { useSessionStore } from '../stores/session';

const router = useRouter();
const route = useRoute();
const store = useSessionStore();
const txt = ref('');
const customers = ref<Customer[]>([]);
const loading = ref(true);
const checking = ref(false);

const load = async () => {
  loading.value = true;
  customers.value = await api.searchCustomers(txt.value);
  loading.value = false;
};

watch(txt, () => {
  clearTimeout(timer);
  timer = window.setTimeout(load, 300);
});

let timer = window.setTimeout(load, 0);

const selectCustomer = (customer: Customer) => {
  store.setCustomer(customer);
  const redirect = route.query.redirect as string;
  if (redirect === 'payment') {
    router.push({ name: 'payment' });
  } else if (redirect === 'ledger') {
    router.push({ name: 'ledger' });
  } else {
    router.push({ name: 'items' });
  }
};

const checkExisting = async (customer: Customer) => {
  checking.value = true;
  try {
    const existing = await api.findDraftOrder(customer.name, store.session?.user);
    if (existing) {
      store.setCurrentOrder(existing.name);
      store.setCartFromOrder(existing.items || []);
      router.push({ name: 'items', query: { customer: customer.name, customer_name: customer.customer_name } });
      return;
    }
    store.setCurrentOrder(null);
    store.clearCart();
    router.push({ name: 'items', query: { customer: customer.name, customer_name: customer.customer_name } });
  } catch (_e) {
    router.push({ name: 'items', query: { customer: customer.name, customer_name: customer.customer_name } });
  } finally {
    checking.value = false;
  }
};
</script>
