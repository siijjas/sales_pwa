<template>
  <WorkspacePage back title="Ledger" :subtitle="customer?.customer_name">
    <template #actions>
      <AppButton variant="ghost" size="sm" icon="refresh" :loading="loading" aria-label="Refresh" @click="loadLedger" />
    </template>
    <template #sticky>
      <SegmentedControl v-model="period" :options="PERIODS" />
    </template>

    <AppAlert v-if="error" tone="danger" :message="error" />
    <SkeletonList v-else-if="loading && !entries.length" :rows="6" height="3.5rem" />

    <div v-else class="space-y-5" :class="loading ? 'opacity-60' : ''">
      <!-- Closing balance -->
      <AppCard padding="lg" class="bg-primary text-primary-fg">
        <p class="text-[11px] font-bold uppercase tracking-[0.08em] opacity-80">Outstanding balance</p>
        <p class="tnum mt-1 text-[30px] font-semibold leading-none tracking-tightest">{{ currency }} {{ money(Math.abs(currentBalance)) }}</p>
        <p class="mt-2 text-[12px] opacity-80">{{ currentBalance < -0.005 ? 'In credit' : 'Owed by the customer' }} · as of {{ shortDate(range.to) }}</p>
      </AppCard>

      <div class="grid grid-cols-3 gap-2.5">
        <KpiTile label="Opening" :value="money(openingBalance)" :sub="shortDate(range.from)" tone="info" />
        <KpiTile label="Invoiced" :value="money(totalDebit)" tone="danger" />
        <KpiTile label="Received" :value="money(totalCredit)" tone="success" />
      </div>

      <section>
        <SectionHeader title="Transactions" :description="entries.length ? plural(entries.length, 'entry', 'entries') : undefined" />
        <EmptyState v-if="!entries.length" icon="ledger" title="No transactions" description="Nothing recorded in this period." />
        <AppCard v-else padding="none" class="divide-y divide-line">
          <ListRow
            v-for="(entry, index) in entriesWithBalance"
            :key="index"
            dense
            :icon="entry.debit > 0 ? 'file-text' : 'banknote'"
            :tone="entry.debit > 0 ? 'danger' : 'success'"
            :title="describe(entry)"
            :subtitle="`${relativeDate(entry.posting_date)} · ${entry.voucher_no}`"
          >
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-[14px] font-bold" :class="entry.debit > 0 ? 'text-danger' : 'text-success'">
                  {{ entry.debit > 0 ? '+' : '−' }} {{ money(entry.debit > 0 ? entry.debit : entry.credit) }}
                </p>
                <p class="tnum text-[11px] text-muted">Bal {{ money(Math.abs(entry.balance)) }}</p>
              </div>
            </template>
          </ListRow>
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import * as api from '../api/frappe';
import type { Customer, LedgerEntry } from '../types';
import { useSessionStore } from '../stores/session';
import { money, plural, relativeDate, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, KpiTile, ListRow, SectionHeader, SegmentedControl, SkeletonList, EmptyState } from '../components/ui';

const PERIODS = [
  { value: 'week', label: '1w' },
  { value: 'month', label: '1m' },
  { value: '3months', label: '3m' },
  { value: '6months', label: '6m' },
];

const route = useRoute();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const name = computed(() => String(route.params.name));

const customer = ref<Customer | null>(null);
const period = ref('month');
const entries = ref<LedgerEntry[]>([]);
const openingBalance = ref(0);
const loading = ref(true);
const error = ref('');

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const range = computed(() => {
  const end = new Date();
  const start = new Date();
  if (period.value === 'week') start.setDate(start.getDate() - 7);
  else if (period.value === 'month') start.setMonth(start.getMonth() - 1);
  else if (period.value === '3months') start.setMonth(start.getMonth() - 3);
  else start.setMonth(start.getMonth() - 6);
  return { from: iso(start), to: iso(end) };
});

interface EntryWithBalance extends LedgerEntry {
  balance: number;
}
const entriesWithBalance = computed<EntryWithBalance[]>(() => {
  let running = openingBalance.value;
  return entries.value.map((entry) => {
    running += entry.debit - entry.credit;
    return { ...entry, balance: running };
  });
});
const currentBalance = computed(() => openingBalance.value + entries.value.reduce((sum, e) => sum + e.debit - e.credit, 0));
const totalDebit = computed(() => entries.value.reduce((sum, e) => sum + e.debit, 0));
const totalCredit = computed(() => entries.value.reduce((sum, e) => sum + e.credit, 0));

const LABELS: Record<string, string> = {
  'Sales Invoice': 'Sales invoice',
  'Payment Entry': 'Payment received',
  'Journal Entry': 'Journal entry',
  'Credit Note': 'Credit note',
  'Debit Note': 'Debit note',
};
const describe = (entry: LedgerEntry) => LABELS[entry.voucher_type] || entry.voucher_type;

async function loadLedger() {
  loading.value = true;
  error.value = '';
  try {
    const result = await api.getCustomerLedger(name.value, range.value.from, range.value.to);
    if (Array.isArray(result)) {
      entries.value = result;
      openingBalance.value = 0;
    } else {
      entries.value = result.entries || [];
      openingBalance.value = result.opening_balance || 0;
    }
  } catch (e: any) {
    error.value = e?.message || 'Could not load the ledger';
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  api.getCustomer(name.value).then((c) => (customer.value = c)).catch(() => (customer.value = null));
  await loadLedger();
});
watch(period, loadLedger);
</script>
