<template>
  <div class="min-h-full bg-gray-50">
    <div class="px-4 py-3 bg-white border-b flex items-center justify-between gap-3 sticky top-0">
      <div class="flex items-center gap-2">
        <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
        <button class="text-sm text-blue-600 font-semibold" @click="$router.push({ name: 'customers' })">
          New Order
        </button>
      </div>
      <div class="flex items-center gap-3">
        <button class="text-sm text-gray-600" @click="$router.push({ name: 'dashboard' })">Dashboard</button>
        <button class="text-sm text-blue-600" @click="reload">Refresh</button>
      </div>
    </div>

    <div class="p-4 space-y-4">
      <div v-if="loading" class="space-y-2">
        <div class="h-24 bg-white rounded-xl shadow-sm animate-pulse" />
        <div class="h-32 bg-white rounded-xl shadow-sm animate-pulse" />
      </div>

      <div v-else-if="error" class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3">
        {{ error }}
      </div>

      <div v-else-if="order" class="space-y-4">
        <div class="bg-white rounded-xl shadow-sm border p-4 space-y-2">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs text-gray-500 uppercase font-semibold">Sales Order</p>
              <p class="text-lg font-semibold text-gray-900">{{ order.name }}</p>
              <p class="text-sm text-gray-600">{{ order.customer_name }} ({{ order.customer }})</p>
              <p class="text-xs text-gray-500">Date: {{ order.transaction_date }}</p>
            </div>
            <div class="flex flex-col items-end gap-2">
              <span class="text-[11px] font-bold px-2 py-1 rounded-full bg-gray-100 text-gray-800 uppercase">{{
                order.status
              }}</span>
              <span
                class="text-[11px] font-semibold px-2 py-1 rounded-full"
                :class="docstatusClass(order.docstatus)"
              >
                {{ docstatusLabel(order.docstatus) }}
              </span>
            </div>
          </div>
          <div class="flex justify-between text-sm text-gray-700 font-semibold">
            <span>Grand Total</span>
            <span>{{ currency }} {{ order.grand_total?.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</span>
          </div>
          <div class="flex justify-between text-xs text-gray-500">
            <span>Company</span>
            <span>{{ order.company || '—' }}</span>
          </div>
          <div class="flex justify-between text-xs text-gray-500">
            <span>Price List</span>
            <span>{{ order.selling_price_list || '—' }}</span>
          </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm border">
          <div class="p-3 border-b text-xs font-semibold text-gray-600 uppercase">
            Items ({{ order.items.length }})
          </div>
          <div class="divide-y">
            <div v-for="line in order.items" :key="line.item_code" class="p-3">
              <div class="flex justify-between">
                <div>
                  <p class="font-semibold text-gray-900">{{ line.item_name }}</p>
                  <p class="text-xs text-gray-500">{{ line.item_code }}</p>
                  <p class="text-xs text-gray-500" v-if="line.stock_uom">UOM: {{ line.stock_uom }}</p>
                </div>
            <div class="text-right">
                  <p class="text-sm font-semibold text-gray-900">{{ currency }} {{ line.rate?.toFixed(2) }}</p>
              <p class="text-xs text-gray-500">Qty: {{ line.qty }}</p>
              <p class="text-xs text-gray-500">Amount: {{ currency }} {{ line.amount?.toFixed(2) }}</p>
            </div>
          </div>
              <p v-if="line.delivery_date" class="text-[11px] text-gray-500 mt-1">
                Delivery: {{ line.delivery_date }}
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm border p-4 space-y-3">
          <div class="flex gap-2 flex-wrap">
            <button
              v-if="order.docstatus === 0"
              class="bg-blue-700 text-white px-4 py-2 rounded-lg disabled:opacity-50"
              :disabled="submitting"
              @click="submitOrder"
            >
              {{ submitting ? 'Submitting...' : 'Submit Order' }}
            </button>
            <button
              v-if="order.docstatus === 0"
              class="bg-blue-600 text-white px-4 py-2 rounded-lg"
              @click="editItems"
            >
              Edit Items
            </button>
            <button
              v-if="order.docstatus === 0"
              class="bg-blue-100 text-blue-700 px-4 py-2 rounded-lg"
              @click="addMoreItems"
            >
              Add Items
            </button>
            <button class="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg" @click="openInDesk">
              Open in ERPNext
            </button>
            <button class="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg" @click="reload">Reload</button>
          </div>
          <p class="text-xs text-gray-500">
            Submit will finalize the draft in ERPNext. Use "Open in ERPNext" for further edits or cancellations.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { SalesOrder } from '../types';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const orderId = route.params.name as string;

const order = ref<SalesOrder | null>(null);
const loading = ref(true);
const error = ref('');
const submitting = ref(false);

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    order.value = await api.getSalesOrder(orderId);
  } catch (e: any) {
    error.value = e?.message || 'Failed to load order';
  } finally {
    loading.value = false;
  }
};

onMounted(load);

const reload = () => load();

const submitOrder = async () => {
  if (!order.value || order.value.docstatus !== 0) return;
  submitting.value = true;
  error.value = '';
  try {
    order.value = await api.getSalesOrder(order.value.name);
    await api.submitSalesOrder(order.value.name);
    await load();
  } catch (e: any) {
    error.value = e?.message || 'Failed to submit order';
  } finally {
    submitting.value = false;
  }
};

const openInDesk = () => {
  const url = `/app/sales-order/${orderId}`;
  window.open(url, '_blank') || router.push({ path: url });
};

const editItems = () => {
  if (!order.value) return;
  store.setCustomer({
    name: order.value.customer,
    customer_name: order.value.customer_name,
    customer_group: '',
    territory: '',
  });
  store.setCurrentOrder(order.value.name);
  store.setCartFromOrder(order.value.items || []);
  router.push({ name: 'cart' });
};

const addMoreItems = () => {
  if (!order.value) return;
  store.setCustomer({
    name: order.value.customer,
    customer_name: order.value.customer_name,
    customer_group: '',
    territory: '',
  });
  store.setCurrentOrder(order.value.name);
  store.setCartFromOrder(order.value.items || []);
  router.push({
    name: 'items',
    query: { customer: order.value.customer, customer_name: order.value.customer_name },
  });
};

const docstatusLabel = (docstatus: number) => {
  if (docstatus === 0) return 'Draft';
  if (docstatus === 1) return 'Submitted';
  if (docstatus === 2) return 'Cancelled';
  return 'Unknown';
};

const docstatusClass = (docstatus: number) => {
  if (docstatus === 1) return 'bg-green-100 text-green-800';
  if (docstatus === 2) return 'bg-red-100 text-red-700';
  return 'bg-yellow-100 text-yellow-800';
};
</script>
