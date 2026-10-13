<template>
  <WorkspacePage title="Activity" :subtitle="customerFilter ? `Customer ${customerFilter}` : undefined">
    <template #actions>
      <AppButton variant="ghost" size="sm" icon="sliders" aria-label="Filter by date" :class="hasDates ? 'text-primary' : ''" @click="filtersOpen = true" />
      <AppButton size="sm" icon="plus" @click="router.push({ name: 'sell' })">New sale</AppButton>
    </template>
    <template #sticky>
      <div class="space-y-2">
        <SegmentedControl :model-value="tab" :options="[{ value: 'orders', label: 'Orders' }, { value: 'payments', label: 'Payments' }]" @update:model-value="setTab" />
        <SearchBar v-model="search" :placeholder="tab === 'orders' ? 'Search by customer or order #…' : 'Search by customer or payment #…'" />
      </div>
    </template>

    <div class="space-y-3">
      <div v-if="hasFilters" class="flex flex-wrap items-center gap-2 px-0.5 text-[12px]">
        <span v-if="hasDates" class="rounded-full bg-card-muted px-2.5 py-1 font-semibold text-muted">{{ dateLabel }}</span>
        <span v-if="customerFilter" class="rounded-full bg-card-muted px-2.5 py-1 font-semibold text-muted">{{ customerFilter }}</span>
        <button type="button" class="font-bold text-primary" @click="clearFilters">Clear</button>
      </div>

      <p v-if="!loading && rows.length" class="px-0.5 text-[12px] text-muted">{{ summaryLine }}</p>

      <AppAlert v-if="error" tone="danger" :message="error" />
      <SkeletonList v-if="loading && !rows.length" :rows="6" height="4rem" />
      <EmptyState
        v-else-if="!rows.length"
        :icon="tab === 'orders' ? 'receipt' : 'wallet'"
        :title="tab === 'orders' ? 'No orders found' : 'No payments found'"
        :description="hasFilters || search ? 'Try different search terms or dates.' : tab === 'orders' ? 'Orders you create appear here.' : 'Payments you collect appear here.'"
      >
        <template v-if="tab === 'orders' && !hasFilters && !search" #action>
          <AppButton icon="plus" @click="router.push({ name: 'sell' })">New sale</AppButton>
        </template>
      </EmptyState>

      <template v-else>
        <AppCard padding="none" class="divide-y divide-line" :class="loading ? 'opacity-60' : ''">
          <template v-if="tab === 'orders'">
            <ListRow
              v-for="o in orders"
              :key="o.name"
              interactive
              chevron
              :title="o.customer_name"
              :subtitle="`${o.name} · ${relativeDate(o.transaction_date)}`"
              @click="router.push({ name: 'order', params: { name: o.name } })"
            >
              <template #leading><Avatar :name="o.customer_name" size="sm" tone="neutral" /></template>
              <template #trailing>
                <div class="text-right">
                  <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(o.grand_total) }}</p>
                  <StatusBadge class="mt-0.5" :status="o.status" :dot="false" />
                </div>
              </template>
            </ListRow>
          </template>
          <template v-else>
            <ListRow
              v-for="p in payments"
              :key="p.name"
              interactive
              chevron
              :title="p.party_name || p.party"
              :subtitle="`${p.name} · ${relativeDate(p.posting_date)}`"
              @click="router.push({ name: 'payment', params: { name: p.name } })"
            >
              <template #leading><Avatar :name="p.party_name || p.party" size="sm" tone="success" /></template>
              <template #trailing>
                <div class="text-right">
                  <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(p.paid_amount) }}</p>
                  <StatusBadge class="mt-0.5" :tone="p.docstatus === 0 ? 'warning' : 'neutral'" :dot="false">{{ p.docstatus === 0 ? 'Draft' : p.mode_of_payment }}</StatusBadge>
                </div>
              </template>
            </ListRow>
          </template>
        </AppCard>
        <AppButton v-if="hasMore" variant="secondary" block :loading="loadingMore" @click="loadMore">Load more</AppButton>
      </template>
    </div>

    <BottomSheet v-model="filtersOpen" title="Filter by date" size="sm">
      <div class="grid grid-cols-2 gap-3">
        <FormField label="From">
          <BaseInput v-model="fromDate" type="date" />
        </FormField>
        <FormField label="To">
          <BaseInput v-model="toDate" type="date" />
        </FormField>
      </div>
      <template #footer>
        <div class="grid grid-cols-2 gap-2.5">
          <AppButton variant="subtle" size="lg" block @click="clearDates">Clear</AppButton>
          <AppButton size="lg" block @click="filtersOpen = false">Done</AppButton>
        </div>
      </template>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { PaymentListRow } from '../api/frappe';
import type { SalesOrder } from '../types';
import { useSessionStore } from '../stores/session';
import { money, plural, relativeDate, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, Avatar, BaseInput, BottomSheet, FormField, ListRow, SearchBar, SegmentedControl, StatusBadge, SkeletonList, EmptyState } from '../components/ui';

const PAGE_LENGTH = 20;
type Tab = 'orders' | 'payments';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);

const tab = computed<Tab>(() => (route.query.tab === 'payments' ? 'payments' : 'orders'));
const customerFilter = computed(() => (typeof route.query.customer === 'string' ? route.query.customer : ''));
const setTab = (v: string) => router.replace({ name: 'activity', query: { ...route.query, tab: v } });

const search = ref('');
const fromDate = ref('');
const toDate = ref('');
const filtersOpen = ref(false);
const hasDates = computed(() => !!(fromDate.value || toDate.value));
const hasFilters = computed(() => hasDates.value || !!customerFilter.value);
const dateLabel = computed(() => {
  if (fromDate.value && toDate.value) return `${shortDate(fromDate.value)} – ${shortDate(toDate.value)}`;
  if (fromDate.value) return `From ${shortDate(fromDate.value)}`;
  return `Until ${shortDate(toDate.value)}`;
});

const orders = ref<SalesOrder[]>([]);
const payments = ref<PaymentListRow[]>([]);
const loading = ref(true);
const loadingMore = ref(false);
const hasMore = ref(false);
const error = ref('');

const rows = computed(() => (tab.value === 'orders' ? orders.value : payments.value));
const summaryLine = computed(() => {
  if (tab.value === 'orders') {
    const total = orders.value.reduce((s, o) => s + (o.grand_total || 0), 0);
    return `${plural(orders.value.length, 'order')}${hasMore.value ? '+' : ''} · ${currency.value} ${money(total)}`;
  }
  const total = payments.value.reduce((s, p) => s + (p.paid_amount || 0), 0);
  return `${plural(payments.value.length, 'payment')}${hasMore.value ? '+' : ''} · ${currency.value} ${money(total)}`;
});

const options = (limitStart: number) => ({
  search: search.value,
  fromDate: fromDate.value || undefined,
  toDate: toDate.value || undefined,
  customer: customerFilter.value || undefined,
  limitStart,
  pageLength: PAGE_LENGTH,
});

let seq = 0;
async function fetchPage(limitStart: number): Promise<number> {
  const user = store.session!.user;
  if (tab.value === 'orders') {
    const page = await api.recentOrders(user, options(limitStart));
    orders.value = limitStart ? [...orders.value, ...page] : page;
    return page.length;
  }
  const page = await api.listPayments(user, options(limitStart));
  payments.value = limitStart ? [...payments.value, ...page] : page;
  return page.length;
}

async function load() {
  if (!store.session) return;
  const mine = ++seq;
  loading.value = true;
  error.value = '';
  try {
    const n = await fetchPage(0);
    if (mine === seq) hasMore.value = n === PAGE_LENGTH;
  } catch (e: any) {
    if (mine === seq) error.value = e?.message || 'Could not load activity';
  } finally {
    if (mine === seq) loading.value = false;
  }
}

async function loadMore() {
  loadingMore.value = true;
  try {
    const n = await fetchPage(rows.value.length);
    hasMore.value = n === PAGE_LENGTH;
  } catch (e: any) {
    error.value = e?.message || 'Could not load more';
  } finally {
    loadingMore.value = false;
  }
}

function clearDates() {
  fromDate.value = '';
  toDate.value = '';
  filtersOpen.value = false;
}
function clearFilters() {
  fromDate.value = '';
  toDate.value = '';
  if (customerFilter.value) router.replace({ name: 'activity', query: { tab: tab.value } });
}

let timer = 0;
watch([search, fromDate, toDate], () => {
  window.clearTimeout(timer);
  timer = window.setTimeout(load, 300);
});
watch([tab, customerFilter], () => {
  orders.value = [];
  payments.value = [];
  hasMore.value = false;
  load();
});
onMounted(load);
</script>
