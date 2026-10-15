<template>
  <WorkspacePage eyebrow="Manager" title="Fleet" :subtitle="`${greeting}${store.firstName ? `, ${store.firstName}` : ''} · ${longDate(new Date())}`" width="wide">
    <template #actions>
      <AppButton variant="secondary" size="sm" icon="refresh" :loading="loading" aria-label="Refresh" @click="load" />
    </template>

    <div class="space-y-6">
      <!-- Hero -->
      <div class="relative overflow-hidden rounded-3xl bg-[#0D3F41] p-5 text-white shadow-raised md:p-6">
        <div class="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-primary/15" />
        <div class="relative flex flex-wrap items-end justify-between gap-4">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#5FD6D0]">Fleet collected today</p>
            <p class="tnum mt-1 text-[38px] font-semibold leading-none tracking-tightest md:text-5xl">{{ currency }} {{ money(t?.collections) }}</p>
            <div class="mt-3 flex flex-wrap items-center gap-2.5 text-[13px] font-medium text-white/80">
              <span>{{ plural(t?.payments_count || 0, 'payment') }}</span>
              <span class="text-white/40">·</span>
              <span>{{ plural(t?.orders_count || 0, 'order') }}</span>
              <span class="text-white/40">·</span>
              <span>{{ plural(data?.vans.length || 0, 'staff member', 'staff') }}</span>
            </div>
          </div>
          <div class="inline-flex items-center gap-2 rounded-full bg-white/12 px-3 py-1.5 text-xs font-semibold">
            <span class="h-[7px] w-[7px] rounded-full" :class="t?.open_shifts ? 'bg-success' : 'bg-white/50'" />
            {{ t?.open_shifts || 0 }} open · {{ t?.closed_shifts || 0 }} closed
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <ActionTile label="New sale" icon="cart" tone="primary" hint="On behalf of a customer" :to="{ name: 'sell' }" />
        <ActionTile label="Counter" icon="monitor" tone="primary" hint="Fast order entry on a PC" :to="{ name: 'counter' }" />
        <ActionTile label="Reports" icon="list" tone="info" hint="Any period, any staff" :to="{ name: 'reports' }" />
        <ActionTile label="Staff" icon="user" tone="success" hint="Profiles and assignments" :to="{ name: 'staff' }" />
        <ActionTile label="Setup" icon="settings" tone="neutral" hint="Invoice options" :to="{ name: 'setup' }" />
      </div>

      <SkeletonList v-if="loading && !data" :rows="3" height="6rem" />
      <AppAlert v-else-if="error" tone="danger" :message="error" />

      <template v-else-if="data">
        <section>
          <SectionHeader title="Fleet today" action-label="Full reports" @action="router.push({ name: 'reports' })" />
          <div class="grid grid-cols-2 gap-2.5 md:grid-cols-3">
            <KpiTile label="Sales" :value="money(t!.sales)" :sub="plural(t!.orders_count, 'order')" icon="cart" tone="primary" interactive @click="drill('sales')" />
            <KpiTile label="Collections" :value="money(t!.collections)" :sub="plural(t!.payments_count, 'payment')" icon="wallet" tone="success" interactive @click="drill('collections')" />
            <KpiTile label="Expenses" :value="money(t!.expenses)" :sub="plural(t!.expenses_count, 'entry', 'entries')" icon="file-text" tone="warning" interactive @click="drill('expenses')" />
            <KpiTile label="Returns" :value="money(t!.returns)" :sub="plural(t!.returns_count, 'credit note')" icon="rotate-ccw" tone="danger" interactive @click="drill('returns')" />
            <KpiTile label="Cash on open shifts" :value="money(t!.expected_cash_open)" :sub="`${t!.open_shifts || 0} on the road`" icon="banknote" tone="info" interactive @click="drill('open_shifts')" />
            <KpiTile label="Avg. order" :value="money(t!.avg_order)" :sub="`Net ${money(t!.net_sales)}`" icon="activity" tone="primary" interactive @click="drill('sales', 'largest')" />
          </div>
        </section>

        <section v-if="data.alerts.length">
          <SectionHeader :title="`Needs attention · ${data.alerts.length}`" />
          <div class="space-y-2">
            <AppAlert v-for="(a, i) in visibleAlerts" :key="`${a.kind}-${a.reference || a.driver}-${i}`" :tone="a.level" :title="a.title">
              {{ a.body }}
              <button v-if="a.kind === 'stale_shift' && a.reference" type="button" class="mt-1.5 block font-semibold underline underline-offset-2" @click="closeShift(a.reference)">Close {{ a.reference }}</button>
              <button v-else-if="(a.kind === 'variance' || a.kind === 'draft_orders') && a.reference" type="button" class="mt-1.5 block font-semibold underline underline-offset-2" @click="router.push({ name: 'closing-report', params: { name: a.reference } })">Open closing report</button>
            </AppAlert>
          </div>
          <button v-if="data.alerts.length > ALERT_LIMIT" class="mt-2 text-xs font-semibold text-primary" @click="showAllAlerts = !showAllAlerts">
            {{ showAllAlerts ? 'Show fewer' : `Show all ${data.alerts.length}` }}
          </button>
        </section>

        <section>
          <SectionHeader title="Staff" action-label="Shift reports" @action="router.push({ name: 'shift-reports' })" />
          <EmptyState v-if="!data.vans.length" icon="users" title="No staff yet" description="Assign staff to a Sales Profile to see them here." />
          <div v-else class="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
            <AppCard v-for="v in data.vans" :key="v.driver" padding="sm" :interactive="Boolean(reportRoute(v))" @click="openVan(v)">
              <div class="flex items-start justify-between gap-3">
                <div class="flex min-w-0 items-center gap-3">
                  <Avatar :name="v.driver_name" size="sm" tone="neutral" />
                  <div class="min-w-0">
                    <p class="truncate font-semibold text-foreground">{{ v.driver_name }}</p>
                    <p class="truncate text-xs text-muted">{{ v.van_name }}{{ v.delivery_route ? ` · ${v.delivery_route}` : '' }}</p>
                  </div>
                </div>
                <StatusBadge :tone="STATUS[v.shift_status].tone" :dot="true">{{ statusLabel(v) }}</StatusBadge>
              </div>
              <div class="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div class="rounded-xl bg-card-muted py-1.5">
                  <p class="text-muted">Sales</p>
                  <p class="tnum font-semibold text-foreground">{{ money(v.sales) }}</p>
                </div>
                <div class="rounded-xl bg-card-muted py-1.5">
                  <p class="text-muted">Collected</p>
                  <p class="tnum font-semibold text-foreground">{{ money(v.collections) }}</p>
                </div>
                <div class="rounded-xl bg-card-muted py-1.5">
                  <template v-if="v.shift_status === 'open'">
                    <p class="text-muted">Cash in hand</p>
                    <p class="tnum font-semibold text-foreground">{{ money(v.expected_cash) }}</p>
                  </template>
                  <template v-else-if="v.shift_status === 'closed'">
                    <p class="text-muted">{{ v.variance_status === 'Within Tolerance' ? 'Within tolerance' : 'Variance' }}</p>
                    <p class="tnum font-semibold" :class="varianceText(v.net_difference, v.variance_status)">{{ signedMoney(v.net_difference) }}</p>
                  </template>
                  <template v-else>
                    <p class="text-muted">Expenses</p>
                    <p class="tnum font-semibold text-foreground">{{ money(v.expenses) }}</p>
                  </template>
                </div>
              </div>
              <AppButton
                v-if="(v.shift_status === 'open' || v.shift_status === 'stale') && v.opening_shift"
                class="mt-3"
                :variant="v.shift_status === 'stale' ? 'warning' : 'secondary'"
                size="sm"
                icon="check-circle"
                block
                @click.stop="closeShift(v.opening_shift)"
              >{{ v.shift_status === 'stale' ? 'Close unclosed shift' : 'Close shift' }}</AppButton>
            </AppCard>
          </div>
        </section>
      </template>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import { useSessionStore } from '../../stores/session';
import type { FleetEntryKind, ManagerDashboard, ManagerDashboardVan } from '../../types';
import { money, signedMoney, plural, longDate, time } from '../../utils/format';
import WorkspacePage from '../WorkspacePage.vue';
import { AppAlert, AppButton, AppCard, ActionTile, Avatar, EmptyState, KpiTile, SectionHeader, SkeletonList, StatusBadge } from '../ui';

const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const greeting = computed(() => {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
});

const ALERT_LIMIT = 3;
const STATUS = {
  open: { tone: 'success', label: 'Shift open' },
  closed: { tone: 'neutral', label: 'Closed' },
  stale: { tone: 'warning', label: 'Stale shift' },
  none: { tone: 'neutral', label: 'Not started' },
} as const;

const data = ref<ManagerDashboard | null>(null);
const loading = ref(true);
const error = ref('');
const showAllAlerts = ref(false);

const t = computed(() => data.value?.totals);
const visibleAlerts = computed(() => (showAllAlerts.value ? data.value!.alerts : data.value!.alerts.slice(0, ALERT_LIMIT)));

const varianceText = (n: number | null, status?: string | null) =>
  !n ? 'text-foreground' : status === 'Within Tolerance' ? 'text-warning' : n > 0 ? 'text-success' : 'text-danger';
const statusLabel = (v: ManagerDashboardVan) => {
  const at = time(v.shift_since);
  if (v.shift_status === 'open' && at) return `Open since ${at}`;
  if (v.shift_status === 'closed' && at) return `Closed ${at}${v.draft_orders_count ? ` · ${plural(v.draft_orders_count, 'draft')}` : ''}`;
  if (v.shift_status === 'none' && v.uses_shifts === false) return 'No shifts';
  return STATUS[v.shift_status].label;
};

const reportRoute = (v: ManagerDashboardVan) => {
  if (v.shift_status === 'open' && v.opening_shift) return { name: 'shift-summary', query: { opening: v.opening_shift } };
  if (v.shift_status === 'closed' && v.closing_shift) return { name: 'closing-report', params: { name: v.closing_shift } };
  return null;
};
const drill = (kind: FleetEntryKind, sort?: 'largest') =>
  router.push({ name: 'fleet-entries', params: { kind }, query: sort ? { sort } : {} });
const closeShift = (opening: string) => router.push({ name: 'shift-close', query: { opening } });
const openVan = (v: ManagerDashboardVan) => {
  const to = reportRoute(v);
  if (to) router.push(to);
};

async function load() {
  loading.value = true;
  error.value = '';
  try {
    data.value = await api.getManagerDashboard();
  } catch (e: any) {
    error.value = e?.message || 'Could not load the fleet dashboard.';
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
