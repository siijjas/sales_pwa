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
              <div class="flex items-center gap-1 mt-1">
                <span class="text-xs text-gray-500">{{ currency }}</span>
                <button 
                  class="text-xs font-semibold text-blue-600 border-b border-blue-200 hover:border-blue-600 px-1"
                  @click="openEdit(line)"
                >
                  {{ itemRate(line).toFixed(2) }}
                </button>
                <span class="text-xs text-gray-500">/ {{ line.item.stock_uom }}</span>
              </div>
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

    <div v-if="editingItem" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click="closeEdit">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden" @click.stop>
        <div class="px-4 py-3 border-b flex justify-between items-center bg-gray-50">
          <h3 class="font-semibold text-gray-900">Edit Price</h3>
          <button class="text-gray-500 hover:text-gray-700" @click="closeEdit">✕</button>
        </div>
        <div class="p-4 space-y-4">
          <div>
            <label class="block text-xs font-semibold text-gray-600 mb-1">Item</label>
            <p class="text-sm text-gray-900">{{ editingItem.item.item_name }}</p>
          </div>
          <div>
            <label class="block text-xs font-semibold text-gray-600 mb-1">New Price ({{ currency }})</label>
            <input
              ref="priceInput"
              type="number"
              v-model.number="editPrice"
              class="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="Enter new price"
              @keyup.enter="savePrice"
            />
          </div>
          <div class="flex gap-2 pt-2">
            <button class="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium" @click="closeEdit">
              Cancel
            </button>
            <button class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium" @click="savePrice">
              Update
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, nextTick } from 'vue';
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

// Edit Price State
const editingItem = ref<CartLine | null>(null);
const editPrice = ref<number>(0);
const priceInput = ref<HTMLInputElement | null>(null);

const openEdit = (line: CartLine) => {
  editingItem.value = line;
  editPrice.value = itemRate(line);
  nextTick(() => {
    priceInput.value?.focus();
    priceInput.value?.select();
  });
};

const closeEdit = () => {
  editingItem.value = null;
  editPrice.value = 0;
};

const savePrice = () => {
  if (editingItem.value) {
    store.updateRate(editingItem.value.item.item_code, editPrice.value);
    closeEdit();
  }
};

const update = (code: string, delta: number) => store.updateQty(code, delta);
const updateRate = (code: string, newRate: number) => store.updateRate(code, newRate);
const clear = () => store.clearCart();
const itemRate = (line: CartLine) => line.rate ?? line.item.price_list_rate ?? line.item.standard_rate ?? 0;

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
      rate: itemRate(line),
      amount: line.qty * itemRate(line),
      delivery_date: today,
      stock_uom: line.item.stock_uom,
      price_list_rate: itemRate(line),
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
