<template>
  <div class="flex flex-col h-full bg-gray-50">
    <div class="px-4 py-3 bg-white border-b flex items-center justify-between sticky top-0">
      <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
      <h2 class="text-base font-semibold text-gray-900">Review Order</h2>
      <button class="text-xs text-red-600" v-if="cart.length" @click="clear">Clear</button>
    </div>

    <div class="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      <div v-if="!customer" class="bg-white rounded-xl p-4 shadow-sm text-sm text-gray-500">
        Select a customer first.
      </div>

      <div v-if="customer" class="bg-white p-4 rounded-xl shadow-sm border">
        <p class="text-xs text-gray-500 uppercase font-semibold mb-1">Customer</p>
        <p class="font-semibold text-gray-900">{{ customer.customer_name }}</p>
        <p class="text-xs text-gray-500">{{ customer.name }}</p>
      </div>

      <div class="bg-white rounded-xl shadow-sm border" v-if="cart.length">
        <div class="p-3 border-b text-xs font-semibold text-gray-600 uppercase">Items ({{ cart.length }})</div>
        <div class="divide-y">
          <div v-for="line in cart" :key="line.item.item_code" class="p-3 flex items-center justify-between">
            <div>
              <p class="font-semibold text-gray-900">{{ line.item.item_name }}</p>
              <p class="text-xs text-gray-500">{{ line.item.item_code }}</p>
              <p class="text-xs text-gray-500">
                {{ currency }} {{ itemRate(line.item).toFixed(2) }} / {{ line.item.stock_uom }}
              </p>
            </div>
            <div class="flex items-center gap-2">
              <button class="px-3 py-1 bg-gray-100 rounded-lg" @click="update(line.item.item_code, -1)">-</button>
              <span class="w-8 text-center font-semibold">{{ line.qty }}</span>
              <button class="px-3 py-1 bg-blue-600 text-white rounded-lg" @click="update(line.item.item_code, 1)">+</button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="bg-white rounded-xl p-4 text-center text-sm text-gray-500 shadow-sm">
        Cart is empty.
      </div>

      <div class="bg-white p-4 rounded-xl shadow-sm border space-y-2">
        <div class="flex justify-between text-sm text-gray-600">
          <span>Net Total</span>
          <span>{{ currency }} {{ net.toFixed(2) }}</span>
        </div>
        <div v-if="tax" class="flex justify-between text-sm text-gray-600">
          <span>Tax</span>
          <span>{{ currency }} {{ tax.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between text-lg font-semibold text-gray-900" :class="tax ? 'border-t pt-2' : ''">
          <span>Grand Total</span>
          <span>{{ currency }} {{ grand.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <div class="p-4 bg-white border-t">
      <button
        class="w-full bg-blue-700 text-white rounded-lg py-3 font-semibold disabled:opacity-50"
        :disabled="submitting || !customer || !cart.length"
        @click="submit"
      >
        {{ submitting ? 'Submitting...' : 'Confirm Order' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import * as api from '../api/frappe';
import type { CartLine, SalesOrder } from '../types';

const store = useSessionStore();
const router = useRouter();

const cart = computed(() => store.cart);
const customer = computed(() => store.customer);
const existingOrder = computed(() => store.currentOrderName);
const net = computed(() => store.cartTotal);
const orderDetail = ref<SalesOrder | null>(null);
const currency = computed(() => store.currencyDisplay);
const tax = computed(() => {
  const t = orderDetail.value?.total_taxes_and_charges;
  return t && t > 0 ? t : 0;
});
const grand = computed(() => net.value + tax.value);
const submitting = ref(false);

const update = (code: string, delta: number) => store.updateQty(code, delta);
const clear = () => store.clearCart();
const itemRate = (item: CartLine['item']) => item.price_list_rate ?? item.standard_rate ?? 0;

onMounted(async () => {
  if (existingOrder.value) {
    try {
      orderDetail.value = await api.getSalesOrder(existingOrder.value);
    } catch (_e) {
      orderDetail.value = null;
    }
  }
});

const submit = async () => {
  if (!customer.value || !cart.value.length) return;
  submitting.value = true;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const itemsPayload = cart.value.map((line) => ({
      item_code: line.item.item_code,
      item_name: line.item.item_name,
      qty: line.qty,
      rate: itemRate(line.item),
      amount: line.qty * itemRate(line.item),
      delivery_date: today,
      stock_uom: line.item.stock_uom,
      price_list_rate: itemRate(line.item),
    }));
    if (existingOrder.value) {
      await api.updateSalesOrder(existingOrder.value, {
        customer: customer.value.name,
        items: itemsPayload,
      });
    } else {
      const res = await api.createSalesOrder({
        customer: customer.value.name,
        items: itemsPayload,
      });
      store.setCurrentOrder(res.name);
    }
    store.clearCart();
    router.push({ name: 'history' });
  } catch (e: any) {
    alert(e?.message || 'Failed to submit order');
  } finally {
    submitting.value = false;
  }
};
</script>
