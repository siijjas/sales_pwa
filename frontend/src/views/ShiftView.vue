<template>
  <WorkspacePage title="Shift" :subtitle="subtitle">
    <template #actions>
      <AppButton variant="secondary" size="sm" icon="refresh" :loading="loading" @click="load">Refresh</AppButton>
    </template>

    <SkeletonList v-if="loading && !loaded" :rows="3" height="6rem" />

    <div v-else class="space-y-6">
      <!-- Manager without a profile: shifts belong to the staff -->
      <AppCard v-if="managerOnly" padding="lg">
        <div class="flex items-start gap-3.5">
          <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><AppIcon name="activity" :size="22" /></span>
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-bold text-foreground">Shifts belong to your staff</p>
            <p class="mt-0.5 text-[13px] leading-relaxed text-muted">See who is on shift and the cash on the road from the Fleet home, and open any closing report from Shift reports.</p>
            <div class="mt-3 flex flex-wrap gap-2">
              <AppButton size="sm" icon="activity" @click="router.push({ name: 'home' })">Fleet</AppButton>
              <AppButton size="sm" variant="secondary" icon="receipt" @click="router.push({ name: 'shift-reports' })">Shift reports</AppButton>
            </div>
          </div>
        </div>
      </AppCard>

      <template v-else>
        <!-- Stale -->
        <AppCard v-if="shift.isStale" padding="lg" class="ring-1 ring-inset ring-warning/30">
          <div class="flex items-start gap-3.5">
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-warning/16 text-warning"><AppIcon name="alert" :size="22" /></span>
            <div class="min-w-0 flex-1">
              <p class="text-[15px] font-bold text-foreground">Your shift from {{ shortDate(shift.active!.shift_date) }} was never closed</p>
              <p class="mt-0.5 text-[13px] leading-relaxed text-muted">Count that day's cash and close it. A new shift can't open until you do.</p>
              <AppButton class="mt-3" size="sm" variant="warning" icon="check-circle" @click="router.push({ name: 'shift-close' })">Close that shift</AppButton>
            </div>
          </div>
        </AppCard>

        <!-- Open -->
        <AppCard v-else-if="shift.isOpen" padding="lg">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.08em] text-success">
                <span class="h-2 w-2 rounded-full bg-success" /> Shift open
              </p>
              <p class="mt-1 text-[22px] font-bold leading-tight tracking-tight text-foreground">Since {{ time(shift.active!.period_start) }}</p>
              <p class="mt-0.5 text-[13px] text-muted">{{ longDate(shift.active!.shift_date) }} · Float {{ currency }} {{ money(shift.active!.opening_float) }}</p>
            </div>
          </div>
          <div class="mt-4 grid gap-2" :class="caps.can_close_shift ? 'grid-cols-2' : ''">
            <AppButton variant="secondary" icon="banknote" block @click="router.push({ name: 'shift-cash' })">Cash out</AppButton>
            <AppButton v-if="caps.can_close_shift" icon="check-circle" block @click="router.push({ name: 'shift-close' })">Close shift</AppButton>
          </div>
          <p v-if="!caps.can_close_shift" class="mt-3 text-[12px] text-muted">Only a manager closes this shift. Let them know when you are done for the day.</p>
        </AppCard>

        <!-- None -->
        <AppCard v-else padding="lg">
          <div class="flex items-start gap-3.5">
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-card-muted text-muted"><AppIcon name="clock" :size="22" /></span>
            <div class="min-w-0 flex-1">
              <p class="text-[15px] font-bold text-foreground">No shift open</p>
              <p class="mt-0.5 text-[13px] leading-relaxed text-muted">
                {{ caps.requires_open_shift ? 'Declare your opening float to start selling.' : 'Open a shift to reconcile cash at the end of the day.' }}
              </p>
              <AppButton class="mt-3" size="sm" icon="play-circle" @click="router.push({ name: 'shift-open' })">Open shift</AppButton>
            </div>
          </div>
        </AppCard>

        <!-- Running figures -->
        <section v-if="shift.isOpen && summary">
          <SectionHeader title="So far" action-label="Full summary" @action="router.push({ name: 'shift-summary' })" />
          <div class="grid grid-cols-2 gap-2.5">
            <KpiTile label="Sales" :value="money(summary.totals.total_sales)" :sub="plural(summary.totals.sales_orders_count, 'order')" icon="cart" tone="primary" />
            <KpiTile label="Collected" :value="money(summary.totals.total_collections)" :sub="plural(summary.totals.payments_count, 'payment')" icon="wallet" tone="success" />
            <KpiTile label="Cash in hand" :value="money(summary.totals.expected_cash)" :sub="`Float ${money(summary.totals.total_opening_float)}`" icon="banknote" tone="info" />
            <KpiTile label="Out of drawer" :value="money(summary.totals.total_expenses + summary.totals.total_deposits)" :sub="`${plural(summary.totals.expenses_count, 'expense')} · ${plural(summary.totals.deposits_count, 'deposit')}`" icon="file-text" tone="warning" />
          </div>
          <AppCard v-if="summary.draft_orders.length" padding="none" class="mt-2.5 ring-1 ring-inset ring-warning/30">
            <div class="px-4 pt-3 text-[12px] font-bold uppercase tracking-[0.08em] text-warning">{{ plural(summary.draft_orders.length, 'draft order') }} not submitted</div>
            <div class="divide-y divide-line">
              <ListRow v-for="d in summary.draft_orders" :key="d.name" interactive chevron dense icon="edit" tone="warning" :title="d.customer_name || d.customer" :subtitle="`${d.name} · ${time(d.creation)}`" @click="router.push({ name: 'order', params: { name: d.name } })">
                <template #trailing><span class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(d.grand_total) }}</span></template>
              </ListRow>
            </div>
          </AppCard>
        </section>

        <!-- Cash movements -->
        <section v-if="shift.isOpen">
          <SectionHeader title="Cash movements this shift" action-label="See all" @action="router.push({ name: 'shift-cash' })" />
          <EmptyState v-if="!movements.length" icon="banknote" title="Nothing yet" description="Expenses and deposits to the office appear here." />
          <AppCard v-else padding="none" class="divide-y divide-line">
            <ListRow
              v-for="m in movements"
              :key="m.name"
              dense
              :icon="m.movement_type === 'Expense' ? 'file-text' : 'banknote'"
              :tone="m.movement_type === 'Expense' ? 'warning' : 'info'"
              :title="m.movement_type === 'Expense' ? (m.expense_account || 'Expense') : 'Deposited to office'"
              :subtitle="[m.against_name, m.remarks].filter(Boolean).join(' · ') || m.name"
            >
              <template #trailing><span class="tnum text-[14px] font-bold text-foreground">− {{ currency }} {{ money(m.amount) }}</span></template>
            </ListRow>
          </AppCard>
        </section>
      </template>

      <!-- Reports -->
      <section>
        <SectionHeader title="Reports" />
        <AppCard padding="none" class="divide-y divide-line">
          <ListRow v-if="shift.isOpen" interactive chevron icon="activity" tone="success" title="Shift summary" subtitle="Everything on the open shift so far" @click="router.push({ name: 'shift-summary' })" />
          <ListRow interactive chevron icon="receipt" tone="primary" title="Shift reports" subtitle="Closing reports for every closed shift" @click="router.push({ name: 'shift-reports' })" />
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { CashMovement, ShiftReport } from '../types';
import { useSessionStore } from '../stores/session';
import { useShiftStore } from '../stores/shift';
import { money, plural, shortDate, longDate, time } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppIcon, EmptyState, KpiTile, ListRow, SectionHeader, SkeletonList } from '../components/ui';

const store = useSessionStore();
const shift = useShiftStore();
const router = useRouter();
const caps = computed(() => store.capabilities);
const currency = computed(() => store.currencyDisplay);
const managerOnly = computed(() => store.isManager && !store.driverConfig);

const loading = ref(true);
const loaded = ref(false);
const summary = ref<ShiftReport | null>(null);
const movements = ref<CashMovement[]>([]);

const subtitle = computed(() => {
  if (managerOnly.value) return 'Fleet overview';
  if (shift.isStale) return 'Needs closing';
  if (shift.isOpen) return `Open since ${time(shift.active!.period_start)}`;
  return 'Not open';
});

async function load() {
  loading.value = true;
  try {
    if (!managerOnly.value) await shift.refresh(true);
    if (!managerOnly.value && shift.isOpen) {
      const [s, m] = await Promise.all([api.getShiftSummary().catch(() => null), api.getShiftCashMovements().catch(() => [] as CashMovement[])]);
      summary.value = s;
      movements.value = m.slice(0, 5);
    } else {
      summary.value = null;
      movements.value = [];
    }
  } finally {
    loading.value = false;
    loaded.value = true;
  }
}
onMounted(load);
</script>
