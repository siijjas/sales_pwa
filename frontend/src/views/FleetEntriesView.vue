<template>
  <WorkspacePage eyebrow="Fleet today" :title="meta.title" :subtitle="longDate(new Date())" width="wide">
    <template #actions>
      <AppButton variant="secondary" size="sm" icon="refresh" :loading="loading" aria-label="Refresh" @click="load" />
    </template>

    <div class="space-y-4 pb-8">
      <!-- Switch between the cards without going back to Fleet -->
      <div class="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5">
        <button
          v-for="k in KINDS"
          :key="k"
          type="button"
          class="focus-ring shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold transition"
          :class="kind === k ? 'bg-primary text-primary-fg' : 'bg-card-muted text-muted hover:text-foreground'"
          @click="router.replace({ name: 'fleet-entries', params: { kind: k } })"
        >{{ META[k].title }}</button>
      </div>

      <SkeletonList v-if="loading && !data" :rows="5" height="4rem" />
      <AppAlert v-else-if="error" tone="danger" :message="error" />

      <template v-else-if="data">
        <div class="grid grid-cols-2 gap-2.5 md:grid-cols-3" :class="{ 'opacity-60': loading }">
          <KpiTile :label="meta.total" :value="money(total)" :sub="plural(shown.length, meta.noun, meta.nouns)" :icon="meta.icon" :tone="meta.tone" />
          <KpiTile v-if="kind === 'sales'" label="Avg. order" :value="money(shown.length ? total / shown.length : 0)" :sub="largest ? `Largest ${money(largest.amount)}` : 'No orders yet'" icon="activity" tone="primary" />
          <KpiTile v-else-if="kind === 'open_shifts'" label="Collected on them" :value="money(sum('collections'))" :sub="`Float ${money(sum('opening_float'))} · spent ${money(sum('expenses'))}`" icon="wallet" tone="success" />
          <KpiTile v-else :label="largest ? 'Largest' : 'Staff'" :value="money(largest?.amount)" :sub="largest ? largest.driver_name : 'Nothing yet'" icon="user" tone="info" />
        </div>

        <!-- By staff: tap to narrow the list -->
        <AppCard v-if="byStaff.length > 1 || driver" padding="lg" class="space-y-3">
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-foreground">By staff</p>
            <button v-if="driver" type="button" class="text-xs font-semibold text-primary" @click="driver = ''">Show all</button>
          </div>
          <button
            v-for="s in byStaff"
            :key="s.driver"
            type="button"
            class="focus-ring block w-full space-y-1 rounded-lg text-left"
            :class="driver && driver !== s.driver ? 'opacity-45' : ''"
            @click="driver = driver === s.driver ? '' : s.driver"
          >
            <div class="flex items-center justify-between gap-3 text-sm">
              <span class="min-w-0 truncate text-foreground">{{ s.driver_name }} <span class="text-xs text-subtle">· {{ s.count }}</span></span>
              <span class="tnum shrink-0 whitespace-nowrap font-semibold text-foreground">{{ money(s.amount) }}</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-card-muted">
              <div class="h-full rounded-full bg-primary" :style="{ width: `${share(s.amount, byStaff[0].amount)}%` }"></div>
            </div>
          </button>
        </AppCard>

        <div v-if="shown.length > 1" class="flex items-center justify-between gap-3 px-0.5">
          <p class="text-[12px] text-muted">{{ plural(shown.length, meta.noun, meta.nouns) }}{{ driverName ? ` · ${driverName}` : '' }}</p>
          <div class="flex gap-1">
            <button
              v-for="o in SORTS"
              :key="o.value"
              type="button"
              class="focus-ring rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="sort === o.value ? 'bg-card-muted text-foreground' : 'text-muted'"
              @click="sort = o.value"
            >{{ o.label }}</button>
          </div>
        </div>

        <EmptyState v-if="!shown.length" :icon="meta.icon" :title="meta.empty" description="They show up here as staff record them." />
        <AppCard v-else padding="none" class="divide-y divide-line" :class="{ 'opacity-60': loading }">
          <ListRow
            v-for="e in sorted"
            :key="e.name"
            :interactive="Boolean(rowRoute(e))"
            :chevron="Boolean(rowRoute(e))"
            @click="open(e)"
          >
            <template #leading><Avatar :name="rowTitle(e)" size="sm" tone="neutral" /></template>
            <template #title>{{ rowTitle(e) }}</template>
            <template #subtitle>{{ rowSubtitle(e) }}</template>
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-[14px] font-bold text-foreground">{{ money(e.amount) }}</p>
                <p class="mt-0.5 text-[11.5px] text-muted">{{ rowNote(e) }}</p>
              </div>
            </template>
          </ListRow>
        </AppCard>
        <p v-if="data.entries.length >= 500" class="px-0.5 text-xs text-muted">Showing the latest 500. Use Reports for the full picture.</p>
      </template>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import type { FleetEntries, FleetEntry, FleetEntryKind } from '../types';
import { money as fmt, plural, longDate, time } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppAlert, AppButton, AppCard, Avatar, EmptyState, KpiTile, ListRow, SkeletonList } from '../components/ui';

type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info';
const KINDS: FleetEntryKind[] = ['sales', 'collections', 'expenses', 'returns', 'open_shifts'];
const META: Record<FleetEntryKind, { title: string; total: string; noun: string; nouns?: string; icon: string; tone: Tone; empty: string }> = {
  sales: { title: 'Sales', total: 'Sales', noun: 'order', icon: 'cart', tone: 'primary', empty: 'No orders today' },
  collections: { title: 'Collections', total: 'Collected', noun: 'payment', icon: 'wallet', tone: 'success', empty: 'No payments today' },
  expenses: { title: 'Expenses', total: 'Spent', noun: 'entry', nouns: 'entries', icon: 'file-text', tone: 'warning', empty: 'No expenses today' },
  returns: { title: 'Returns', total: 'Returned', noun: 'credit note', icon: 'rotate-ccw', tone: 'danger', empty: 'No returns today' },
  open_shifts: { title: 'Cash on open shifts', total: 'Expected cash', noun: 'open shift', icon: 'banknote', tone: 'info', empty: 'No shifts open' },
};
const SORTS = [
  { value: 'latest', label: 'Latest' },
  { value: 'largest', label: 'Largest' },
] as const;

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const money = (n?: number | null) => `${store.currencyDisplay} ${fmt(n)}`;

const kind = computed<FleetEntryKind>(() => {
  const k = route.params.kind as FleetEntryKind;
  return KINDS.includes(k) ? k : 'sales';
});
const meta = computed(() => META[kind.value]);

const data = ref<FleetEntries | null>(null);
const loading = ref(true);
const error = ref('');
const driver = ref(typeof route.query.driver === 'string' ? route.query.driver : '');
const sort = ref<'latest' | 'largest'>(route.query.sort === 'largest' ? 'largest' : 'latest');

const entries = computed(() => (data.value?.kind === kind.value ? data.value.entries : []));
const shown = computed(() => entries.value.filter((e) => !driver.value || e.driver === driver.value));
const sorted = computed(() =>
  sort.value === 'largest' ? [...shown.value].sort((a, b) => b.amount - a.amount) : shown.value,
);
const total = computed(() => shown.value.reduce((s, e) => s + (e.amount || 0), 0));
const largest = computed(() => shown.value.reduce<FleetEntry | null>((m, e) => (!m || e.amount > m.amount ? e : m), null));
const sum = (key: 'collections' | 'expenses' | 'opening_float') => shown.value.reduce((s, e) => s + (e[key] || 0), 0);
const share = (part: number, whole: number) => (whole > 0 ? Math.max(0, Math.min(100, (part / whole) * 100)) : 0);

const byStaff = computed(() => {
  const map = new Map<string, { driver: string; driver_name: string; count: number; amount: number }>();
  for (const e of entries.value) {
    const row = map.get(e.driver) || { driver: e.driver, driver_name: e.driver_name, count: 0, amount: 0 };
    row.count += 1;
    row.amount += e.amount || 0;
    map.set(e.driver, row);
  }
  return [...map.values()].sort((a, b) => b.amount - a.amount);
});
const driverName = computed(() => byStaff.value.find((s) => s.driver === driver.value)?.driver_name || '');

const rowTitle = (e: FleetEntry) => {
  if (kind.value === 'expenses') return e.expense_type || 'Expense';
  if (kind.value === 'open_shifts') return e.driver_name;
  return e.customer_name || e.customer || e.name;
};
const rowSubtitle = (e: FleetEntry) => {
  const at = time(e.creation);
  switch (kind.value) {
    case 'expenses':
      return [e.driver_name, e.remarks, at].filter(Boolean).join(' · ');
    case 'returns':
      return [e.name, e.return_against ? `against ${e.return_against}` : '', e.driver_name].filter(Boolean).join(' · ');
    case 'open_shifts':
      return [e.van_name, e.since ? `open since ${time(e.since)}` : ''].filter(Boolean).join(' · ');
    default:
      return [e.name, e.driver_name, at].filter(Boolean).join(' · ');
  }
};
const rowNote = (e: FleetEntry) => {
  switch (kind.value) {
    case 'sales':
      return e.status || '';
    case 'collections':
      return e.mode_of_payment || '';
    case 'open_shifts':
      return `Collected ${fmt(e.collections)}`;
    case 'returns':
      return time(e.creation);
    default:
      return '';
  }
};
const rowRoute = (e: FleetEntry) => {
  if (kind.value === 'sales') return { name: 'order', params: { name: e.name } };
  if (kind.value === 'collections') return { name: 'payment', params: { name: e.name } };
  if (kind.value === 'open_shifts') return { name: 'shift-summary', query: { opening: e.name } };
  if (kind.value === 'returns' && e.customer) return { name: 'customer', params: { name: e.customer } };
  return null;
};
const open = (e: FleetEntry) => {
  const to = rowRoute(e);
  if (to) router.push(to);
};

let seq = 0;
async function load() {
  const mine = ++seq;
  loading.value = true;
  error.value = '';
  try {
    const res = await api.getFleetEntries(kind.value);
    if (mine === seq) data.value = res;
  } catch (e: any) {
    if (mine === seq) error.value = e?.message || 'Could not load these entries.';
  } finally {
    if (mine === seq) loading.value = false;
  }
}
watch(kind, load, { immediate: true });
</script>
