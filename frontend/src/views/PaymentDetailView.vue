<template>
  <div class="bg-gray-50 min-h-screen">
    <div v-if="loading" class="flex justify-center items-center h-screen">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>

    <div v-else-if="payment" class="px-4 py-4">
      <div class="flex items-center gap-3 mb-6">
        <button 
          class="bg-white p-2 rounded-lg border border-gray-200 shadow-sm"
          @click="$router.back()"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-600"><path d="m15 18-6-6 6-6"/></svg>
        </button>
        <h1 class="text-xl font-bold text-gray-900">Payment Details</h1>
      </div>

      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-4">
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-xs text-gray-500 uppercase font-semibold">Customer</p>
            <p class="text-lg font-bold text-gray-900">{{ payment.party_name }}</p>
          </div>
          <span class="bg-emerald-50 text-emerald-600 text-xs font-bold px-2 py-1 rounded-full uppercase">
            {{ payment.status }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p class="text-xs text-gray-500 uppercase font-semibold">Date</p>
            <p class="text-sm font-medium text-gray-900">{{ formatDate(payment.posting_date) }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 uppercase font-semibold">Mode</p>
            <p class="text-sm font-medium text-gray-900">{{ payment.mode_of_payment }}</p>
          </div>
        </div>

        <div class="pt-4 border-t border-gray-100">
          <p class="text-xs text-gray-500 uppercase font-semibold mb-1">Amount Paid</p>
          <p class="text-2xl font-bold text-gray-900">{{ currency }} {{ payment.paid_amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
        </div>
      </div>

      <div v-if="payment.references && payment.references.length > 0" class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
        <h3 class="text-sm font-bold text-gray-900 mb-3">Allocated To</h3>
        <div class="space-y-3">
          <div 
            v-for="ref in payment.references" 
            :key="ref.name"
            class="flex justify-between items-center py-2 border-b border-gray-50 last:border-0"
          >
            <div>
              <p class="text-sm font-semibold text-gray-900">{{ ref.reference_name }}</p>
              <p class="text-xs text-gray-500">{{ ref.reference_doctype }}</p>
            </div>
            <p class="text-sm font-bold text-gray-900">{{ currency }} {{ ref.allocated_amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { getPaymentEntry } from '../api/frappe';

const route = useRoute();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const payment = ref<any>(null);
const loading = ref(true);

onMounted(async () => {
  const name = route.params.name as string;
  if (name) {
    try {
      payment.value = await getPaymentEntry(name);
    } finally {
      loading.value = false;
    }
  }
});

const formatDate = (date: string) => {
  if (!date) return '';
  return new Date(date).toLocaleDateString();
};
</script>
