<template>
  <div class="flex flex-col h-full bg-gray-50">
    <div class="px-4 py-3 bg-white border-b flex items-center gap-2 sticky top-0">
      <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
      <div class="flex-1">
        <p class="text-xs text-gray-500">Customer</p>
        <p class="text-sm font-semibold text-gray-900 truncate">{{ customerName }}</p>
      </div>
    </div>

    <div class="px-4 py-3">
      <input
        v-model="search"
        class="w-full bg-white border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
        placeholder="Search items"
      />
    </div>

    <div class="flex-1 overflow-y-auto px-4 pb-24">
      <div v-if="loading" class="space-y-3">
        <div class="h-24 bg-white rounded-xl shadow-sm animate-pulse" />
        <div class="h-24 bg-white rounded-xl shadow-sm animate-pulse" />
      </div>
      <div v-else class="space-y-3">
        <div v-if="error" class="bg-red-50 text-red-700 text-sm p-3 rounded-lg border border-red-200">
          {{ error }}
        </div>
        <div
          v-for="item in items"
          :key="item.item_code"
          class="bg-white rounded-xl border border-gray-100 p-3 shadow-sm flex justify-between items-center"
        >
          <div>
            <p class="font-semibold text-gray-900">{{ item.item_name }}</p>
            <p class="text-xs text-gray-500">{{ item.item_code }}</p>
            <p class="text-sm font-bold text-gray-900 mt-1">
              <span v-if="itemPrice(item) !== null">{{ currency }} {{ itemPrice(item)?.toFixed(2) }}</span>
              <span v-else class="text-xs font-semibold text-gray-500">Price unavailable</span>
            </p>
            <p v-if="hasQty(item) && item.actual_qty! <= 0" class="text-xs font-semibold text-red-600">Out of stock</p>
            <p v-else-if="hasQty(item) && item.actual_qty! < 5" class="text-xs text-orange-600">
              Only {{ item.actual_qty }} left
            </p>
            <p v-else-if="hasQty(item)" class="text-xs text-gray-600">Available: {{ item.actual_qty }}</p>
          </div>
          <div class="flex items-center gap-2">
            <button class="px-3 py-2 bg-gray-100 rounded-lg" @click="update(item.item_code, -1)">-</button>
            <span class="w-8 text-center font-semibold">{{ getQty(item.item_code) }}</span>
            <button class="px-3 py-2 bg-blue-600 text-white rounded-lg" @click="add(item)">+</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="cartCount" class="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg p-4">
      <div class="max-w-md mx-auto flex items-center justify-between">
        <div>
          <p class="text-xs text-gray-500">Cart</p>
          <p class="font-bold text-gray-900">₹ {{ total }}</p>
        </div>
        <button class="bg-blue-700 text-white px-4 py-2 rounded-lg" @click="$router.push({ name: 'cart' })">
          View Cart
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { Item } from '../types';
import { useSessionStore } from '../stores/session';

const store = useSessionStore();
const route = useRoute();
const router = useRouter();
const customerParam = route.query.customer as string | undefined;
const customerNameParam = route.query.customer_name as string | undefined;

const search = ref('');
const items = ref<Item[]>([]);
const loading = ref(true);
const error = ref('');
const currency = computed(() => store.currencyDisplay);

const cartCount = computed(() => store.cartCount);
const total = computed(() => store.cartTotal.toFixed(2));

const loadItems = async () => {
  loading.value = true;
  error.value = '';
  try {
    items.value = await api.listItems(search.value, store.customer?.name);
  } catch (e: any) {
    error.value = e?.message || 'Failed to load items';
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  if (customerParam && customerNameParam) {
    store.setCustomer({ name: customerParam, customer_name: customerNameParam, customer_group: '', territory: '' });
  }
  if (!store.customer) {
    router.push({ name: 'customers' });
    return;
  }
  if (store.currentOrderName && store.cart.length === 0) {
    // ensure existing order items are in cart when resuming
    api.getSalesOrder(store.currentOrderName).then((order) => {
      store.setCartFromOrder(order.items || []);
    });
  }
  loadItems();
});

watch(search, () => {
  clearTimeout(timer);
  timer = window.setTimeout(loadItems, 300);
});

let timer = window.setTimeout(() => {}, 0);

function add(item: Item) {
  if (item.actual_qty !== undefined && item.actual_qty <= 0) return;
  store.addToCart(item);
}

function update(itemCode: string, delta: number) {
  store.updateQty(itemCode, delta);
}

function getQty(itemCode: string) {
  return store.cart.find((line) => line.item.item_code === itemCode)?.qty || 0;
}

const customerName = computed(() => store.customer?.customer_name || customerNameParam || '');
const itemPrice = (item: Item) => item.price_list_rate ?? item.standard_rate ?? 0;
const hasQty = (item: Item) => item.actual_qty !== undefined && item.actual_qty !== null;
</script>
