<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="px-4 py-3 bg-white border-b sticky top-0 z-10">
      <div class="flex items-center justify-between gap-2 mb-2">
        <div class="flex items-center gap-2">
          <button class="text-sm text-gray-600" @click="$router.back()">Back</button>
          <h2 class="text-base font-semibold text-gray-900">Customer Ledger</h2>
        </div>
        <div class="flex items-center gap-3">
          <button class="text-sm text-gray-600" @click="$router.push({ name: 'dashboard' })">Dashboard</button>
          <button class="text-sm text-blue-600" @click="reload">Refresh</button>
        </div>
      </div>
      
      <!-- Customer Selector -->
      <div class="mb-2">
        <div v-if="customer" class="bg-blue-50 border border-blue-100 px-3 py-2 rounded-lg flex justify-between items-center" @click="changeCustomer">
          <p class="text-sm font-bold text-gray-900">{{ customer.customer_name }}</p>
          <span class="text-xs text-blue-600 font-medium">Change</span>
        </div>
        <button
          v-else
          class="w-full bg-white border border-dashed border-gray-300 rounded-lg py-2 text-sm text-gray-500"
          @click="$router.push({ name: 'customers', query: { redirect: 'ledger' } })"
        >+ Select Customer</button>
      </div>

      <!-- Duration Filter -->
      <div>
        <label class="block text-[10px] font-semibold text-gray-400 uppercase mb-0.5">Period</label>
        <select v-model="selectedPeriod" class="w-full bg-gray-50 border border-gray-200 rounded px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-blue-500">
          <option value="week">Last Week</option>
          <option value="month">Last Month</option>
          <option value="3months">Last 3 Months</option>
          <option value="6months">Last 6 Months</option>
        </select>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto">
      <!-- Opening Balance Summary -->
      <div v-if="customer && !loading && entries.length > 0" class="px-4 pt-4">
        <div class="bg-white rounded-xl border border-gray-200 px-4 py-2.5 shadow-sm">
          <p class="text-[10px] text-gray-400 uppercase">Opening Balance</p>
          <p class="text-base font-bold text-gray-900">{{ currency }} {{ openingBalance.toFixed(2) }}</p>
        </div>
      </div>

      <!-- Invoiced & Received Summary -->
      <div v-if="customer && !loading && entries.length > 0" class="px-4 pt-3">
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-white rounded-xl border border-gray-200 px-4 py-2.5 shadow-sm">
            <p class="text-[10px] text-gray-400 uppercase">Invoiced</p>
            <p class="text-base font-bold text-red-600">{{ currency }} {{ totalDebit.toFixed(2) }}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 px-4 py-2.5 shadow-sm">
            <p class="text-[10px] text-gray-400 uppercase">Received</p>
            <p class="text-base font-bold text-green-600">{{ currency }} {{ totalCredit.toFixed(2) }}</p>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="px-4 pt-4 space-y-2">
        <div v-for="i in 6" :key="i" class="bg-white h-14 rounded-lg animate-pulse" />
      </div>

      <!-- Empty State -->
      <div v-else-if="entries.length === 0 && customer" class="px-4 pt-10 text-center">
        <p class="text-gray-400 text-sm">No transactions found for this period.</p>
      </div>

      <!-- Transaction List -->
      <div v-else-if="entries.length > 0" class="px-4 pt-3">
        <p class="text-[10px] font-bold text-gray-400 uppercase mb-2 px-1">{{ entries.length }} Transactions</p>
        
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden divide-y divide-gray-100">
          <div
            v-for="(entry, index) in entriesWithBalance"
            :key="index"
            class="px-3 py-2.5 flex items-center gap-3"
          >
            <!-- Icon -->
            <div 
              class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
              :class="entry.debit > 0 ? 'bg-red-50' : 'bg-green-50'"
            >
              <span class="text-sm" v-if="entry.debit > 0">📄</span>
              <span class="text-sm" v-else>💵</span>
            </div>
            
            <!-- Details -->
            <div class="flex-1 min-w-0">
              <div class="flex justify-between items-start">
                <div class="min-w-0 pr-2">
                  <p class="text-sm font-medium text-gray-900 truncate">
                    {{ getDescription(entry) }}
                  </p>
                  <p class="text-[10px] text-gray-400">{{ formatDate(entry.posting_date) }} · {{ entry.voucher_no }}</p>
                </div>
                <div class="text-right shrink-0">
                  <p 
                    class="text-sm font-bold tabular-nums"
                    :class="entry.debit > 0 ? 'text-red-600' : 'text-green-600'"
                  >
                    {{ entry.debit > 0 ? '+' : '-' }} {{ currency }} {{ (entry.debit > 0 ? entry.debit : entry.credit).toFixed(2) }}
                  </p>
                  <p class="text-[10px] text-gray-400 tabular-nums">Bal: {{ currency }} {{ Math.abs(entry.balance).toFixed(2) }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Outstanding Balance at Bottom -->
      <div v-if="customer && !loading && entries.length > 0" class="px-4 pt-3 pb-20">
        <div class="bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-xl px-4 py-4 shadow-lg">
          <p class="text-xs opacity-90 uppercase font-semibold">Outstanding Balance</p>
          <p class="text-2xl font-bold mt-1">
            {{ currency }} {{ Math.abs(currentBalance).toFixed(2) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import * as api from '../api/frappe';
import type { LedgerEntry } from '../types';

const store = useSessionStore();
const route = useRoute();
const router = useRouter();

const customer = computed(() => store.customer);
const currency = computed(() => store.currencyDisplay);

const selectedPeriod = ref('week');
const entries = ref<LedgerEntry[]>([]);
const loading = ref(false);

const dateRange = computed(() => {
  const end = new Date();
  const start = new Date();
  
  switch (selectedPeriod.value) {
    case 'week':
      start.setDate(start.getDate() - 7);
      break;
    case 'month':
      start.setMonth(start.getMonth() - 1);
      break;
    case '3months':
      start.setMonth(start.getMonth() - 3);
      break;
    case '6months':
      start.setMonth(start.getMonth() - 6);
      break;
  }
  
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10)
  };
});

const customerParam = route.query.customer as string | undefined;
const customerNameParam = route.query.customer_name as string | undefined;

interface EntryWithBalance extends LedgerEntry {
  balance: number;
}

const entriesWithBalance = computed(() => {
  let running = 0;
  return entries.value.map(entry => {
    running += (entry.debit - entry.credit);
    return { ...entry, balance: running };
  }); // Oldest to newest (chronological)
}); 

const currentBalance = computed(() => {
  if (entries.value.length === 0) return 0;
  return entries.value.reduce((sum, e) => sum + e.debit - e.credit, 0);
});

const openingBalance = computed(() => {
  if (entriesWithBalance.value.length === 0) return 0;
  // Opening balance is the balance before the first transaction in the period
  // which is 0 if we're showing from the beginning, or we'd need to fetch it from API
  // For now, we'll assume opening is 0 and calculate from there
  return 0;
});

const closingBalance = computed(() => {
  if (entriesWithBalance.value.length === 0) return 0;
  // Closing balance is the balance after the last transaction
  return entriesWithBalance.value[entriesWithBalance.value.length - 1].balance;
});

const totalDebit = computed(() => entries.value.reduce((sum, e) => sum + e.debit, 0));
const totalCredit = computed(() => entries.value.reduce((sum, e) => sum + e.credit, 0));


const getDescription = (entry: EntryWithBalance): string => {
  const labels: Record<string, string> = {
    'Sales Invoice': 'Sales Invoice',
    'Payment Entry': 'Payment Received',
    'Journal Entry': 'Journal Entry',
    'Credit Note': 'Credit Note',
    'Debit Note': 'Debit Note',
  };
  return labels[entry.voucher_type] || entry.voucher_type;
};

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

onMounted(() => {
  if (customerParam && customerNameParam) {
    store.setCustomer({ name: customerParam, customer_name: customerNameParam, customer_group: '', territory: '' });
  }
  if (customer.value) loadLedger();
});

const reload = () => {
  if (customer.value) loadLedger();
};

const loadLedger = async () => {
  if (!customer.value) return;
  loading.value = true;
  try {
    entries.value = await api.getCustomerLedger(customer.value.name, dateRange.value.from, dateRange.value.to);
  } catch (e) {
    console.error('Failed to load ledger', e);
  } finally {
    loading.value = false;
  }
};

const changeCustomer = () => {
  store.setCustomer(null);
  entries.value = [];
};

watch([customer, selectedPeriod], () => {
  if (customer.value) loadLedger();
});
</script>
