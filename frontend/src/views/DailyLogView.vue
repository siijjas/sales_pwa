<template>
  <div class="bg-gray-50 min-h-screen">
    <div class="px-4 py-4">
      <div class="flex items-center gap-3 mb-6">
        <button 
          class="bg-white p-2 rounded-lg border border-gray-200 shadow-sm"
          @click="$router.push({ name: 'dashboard' })"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-600"><path d="m15 18-6-6 6-6"/></svg>
        </button>
        <h1 class="text-xl font-bold text-gray-900">{{ title }}</h1>
      </div>

      <div v-if="loading" class="space-y-3">
        <div v-for="i in 3" :key="i" class="h-20 bg-white rounded-xl shadow-sm animate-pulse" />
      </div>

      <div v-else>
        <!-- Payment Summary Card -->
        <div v-if="isPayments && items.length > 0" class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 mb-4">
          <div class="mb-3">
            <p class="text-xs text-gray-500 uppercase font-semibold">Total Collection</p>
            <p class="text-2xl font-bold text-gray-900">{{ currency }} {{ totalCollection.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div 
              v-for="(amount, mode) in collectionBreakdown" 
              :key="mode"
              class="bg-gray-50 p-2 rounded-lg"
            >
              <p class="text-xs text-gray-500 font-medium truncate">{{ mode }}</p>
              <p class="text-sm font-bold text-gray-900">{{ currency }} {{ amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</p>
            </div>
          </div>
        </div>

        <div v-if="items.length === 0" class="flex flex-col items-center justify-center p-8 bg-white rounded-xl shadow-sm text-center">
          <div class="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>
          </div>
          <p class="text-gray-500 font-medium">No transactions found for today</p>
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="item in items"
            :key="item.name"
            class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 active:scale-[0.98] transition-transform"
            @click="openDetail(item)"
          >
            <div class="flex justify-between items-start mb-1">
              <div>
                <p class="font-semibold text-gray-900">{{ item.customer_name || item.party_name }}</p>
                <p class="text-xs text-gray-500">{{ item.name }}</p>
              </div>
              <div class="flex flex-col items-end gap-1">
                <span 
                  class="text-xs font-bold px-2 py-1 rounded-full uppercase"
                  :class="getStatusColor(item.status)"
                >
                  {{ item.status }}
                </span>
                <span v-if="isPayments && item.mode_of_payment" class="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded border border-gray-200">
                  {{ item.mode_of_payment }}
                </span>
              </div>
            </div>
            <div class="flex justify-between items-end mt-2">
              <p class="text-xs text-gray-400 font-medium">{{ formatDate(item.transaction_date || item.posting_date) }}</p>
              <p class="text-sm font-bold text-gray-900">
                {{ currency }} {{ (item.grand_total || item.paid_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { getDailyLog } from '../api/frappe';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);

const type = computed(() => route.params.type as string);
const isPayments = computed(() => type.value === 'payments');
const title = computed(() => type.value === 'orders' ? "Today's Orders" : "Today's Payments");
const doctype = computed(() => type.value === 'orders' ? 'Sales Order' : 'Payment Entry');

const items = ref<any[]>([]);
const loading = ref(true);

const totalCollection = computed(() => {
  if (!isPayments.value) return 0;
  return items.value.reduce((sum, item) => sum + (item.paid_amount || 0), 0);
});

const collectionBreakdown = computed(() => {
  if (!isPayments.value) return {};
  return items.value.reduce((acc, item) => {
    const mode = item.mode_of_payment || 'Unknown';
    acc[mode] = (acc[mode] || 0) + (item.paid_amount || 0);
    return acc;
  }, {} as Record<string, number>);
});

const fetchLog = async () => {
  loading.value = true;
  items.value = []; // Clear previous items to avoid stale data flash
  try {
    items.value = await getDailyLog(doctype.value);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchLog();
});

watch(() => route.params.type, () => {
  fetchLog();
});

const openDetail = (item: any) => {
  if (type.value === 'orders') {
    router.push({ name: 'order-detail', params: { name: item.name } });
  } else {
    router.push({ name: 'payment-detail', params: { name: item.name } });
  }
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    Draft: 'bg-gray-100 text-gray-600',
    Submitted: 'bg-blue-50 text-blue-600',
    Cancelled: 'bg-red-50 text-red-600',
    Completed: 'bg-emerald-50 text-emerald-600',
    Overdue: 'bg-orange-50 text-orange-600',
    Paid: 'bg-emerald-50 text-emerald-600',
    Unpaid: 'bg-red-50 text-red-600',
  };
  return colors[status] || 'bg-gray-100 text-gray-600';
};

const formatDate = (date: string) => {
  if (!date) return '';
  return new Date(date).toLocaleDateString();
};
</script>
