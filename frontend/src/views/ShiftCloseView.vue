<template>
  <WorkspacePage :back="{ name: 'shift' }" title="Close shift" :subtitle="summary ? (isOwnShift ? longDate(summary.shift_date) : `${summary.driver_name} · ${longDate(summary.shift_date)}`) : 'Count and reconcile'">
    <SkeletonList v-if="loading" :rows="3" height="7rem" />

    <div v-else-if="summary" class="space-y-4 pb-28">
      <AppAlert
        v-if="summary.is_stale || !isOwnShift"
        tone="warning"
        :title="closingTitle"
        :message="summary.is_stale
          ? 'This shift was never closed. It closes as that day: the figures below are that day\'s sales, collections and expenses. Count the cash that belongs to it.'
          : 'You are closing this shift on their behalf. The closing records that you closed it.'"
      />
      <AppAlert v-if="summary.draft_orders.length" tone="warning" :title="`${plural(summary.draft_orders.length, 'draft order')} not submitted`">
        Drafts are not counted in this closing. Submit or discard them first, or close anyway and the closing will note them.
        <ul class="mt-2 space-y-1">
          <li v-for="d in summary.draft_orders" :key="d.name">
            <button type="button" class="font-semibold underline underline-offset-2" @click="router.push({ name: 'order', params: { name: d.name } })">{{ d.name }}</button>
            <span class="opacity-90"> · {{ d.customer_name || d.customer }} · {{ currency }} {{ money(d.grand_total) }}</span>
          </li>
        </ul>
      </AppAlert>
      <AppAlert
        v-if="outsideCount"
        tone="info"
        title="Activity before this shift opened"
        :message="`${outsideText} on ${shortDate(summary.shift_date)} before the shift opened and on no other closing. They are not in this closing's totals.`"
      />
      <AppAlert
        v-if="summary.blind"
        tone="info"
        title="Blind count"
        message="Count each payment mode and enter what you actually have. Your profile hides the expected amounts; your manager sees the difference on the closing report."
      />

      <div class="grid grid-cols-2 gap-2.5">
        <KpiTile label="Total sales" :value="money(summary.total_sales)" :sub="`${qty(summary.total_quantity)} units · tax ${money(summary.total_taxes)}`" icon="cart" tone="primary" />
        <KpiTile label="Collections" :value="money(summary.total_collections)" icon="wallet" tone="success" />
        <KpiTile label="Opening float" :value="money(summary.total_opening_float)" icon="briefcase" tone="info" />
        <KpiTile v-if="!summary.blind" label="Expected cash" :value="money(summary.expected_cash ?? 0)" icon="banknote" tone="primary" />
        <KpiTile v-if="summary.total_expenses > 0" :class="summary.total_deposits > 0 ? '' : 'col-span-2'" label="Expenses paid" :value="money(summary.total_expenses)" icon="file-text" tone="warning" />
        <KpiTile v-if="summary.total_deposits > 0" :class="summary.total_expenses > 0 ? '' : 'col-span-2'" label="Deposited to office" :value="money(summary.total_deposits)" icon="banknote" tone="info" />
      </div>

      <AppCard padding="lg" class="space-y-4">
        <div>
          <p class="text-[15px] font-bold text-foreground">Count the drawer</p>
          <p class="mt-0.5 text-[13px] text-muted">Enter what you actually hold in each mode.</p>
        </div>

        <div v-for="row in rows" :key="row.mode_of_payment" class="space-y-2 rounded-2xl bg-card-muted p-3">
          <div class="flex items-center justify-between">
            <span class="text-[14px] font-bold text-foreground">{{ row.mode_of_payment }}</span>
            <span v-if="!summary.blind && diff(row) !== 0" class="tnum text-xs font-bold" :class="diff(row) > 0 ? 'text-success' : 'text-danger'">
              {{ diff(row) > 0 ? '+' : '−' }}{{ currency }} {{ money(Math.abs(diff(row))) }}
            </span>
          </div>
          <div class="grid gap-2 text-xs" :class="summary.blind ? 'grid-cols-1' : 'grid-cols-2'">
            <div class="rounded-xl bg-card px-2 py-1.5 text-center">
              <p class="text-muted">Opening</p>
              <p class="tnum font-semibold text-foreground">{{ money(row.opening_amount) }}</p>
            </div>
            <div v-if="!summary.blind" class="rounded-xl bg-card px-2 py-1.5 text-center">
              <p class="text-muted">Expected</p>
              <p class="tnum font-semibold text-foreground">{{ money(row.expected_amount ?? 0) }}</p>
            </div>
          </div>
          <div>
            <p class="mb-1 text-xs font-semibold text-muted">Counted</p>
            <BaseInput v-model="row.closing_amount" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" min="0" step="0.01" />
          </div>
        </div>

        <div
          v-if="!summary.blind && netDifference !== 0"
          class="flex items-center justify-between rounded-2xl px-4 py-3 ring-1 ring-inset"
          :class="varianceStatus === 'Within Tolerance'
            ? 'bg-warning/10 text-warning ring-warning/25'
            : netDifference > 0 ? 'bg-success/10 text-success ring-success/25' : 'bg-danger/10 text-danger ring-danger/25'"
        >
          <div>
            <p class="text-[14px] font-semibold">Net variance · {{ varianceStatus }}</p>
            <p class="text-xs opacity-90">
              {{ netDifference > 0 ? 'More than expected.' : 'Less than expected.' }}
              <template v-if="summary.variance_tolerance">
                {{ varianceStatus === 'Within Tolerance' ? 'Within' : 'Beyond' }} the {{ currency }} {{ money(summary.variance_tolerance) }} tolerance.
              </template>
              <template v-else>Your manager will see this flagged.</template>
            </p>
          </div>
          <span class="tnum text-[18px] font-bold">{{ netDifference > 0 ? '+' : '−' }}{{ currency }} {{ money(Math.abs(netDifference)) }}</span>
        </div>

        <FormField label="Notes" hint="Optional — explain any variance.">
          <BaseTextarea v-model="notes" :rows="2" placeholder="Leave notes for the cashier…" />
        </FormField>
      </AppCard>

      <AppAlert v-if="error" tone="danger" :message="error" />
    </div>

    <div v-else class="space-y-4">
      <AppAlert tone="danger" :message="error || 'No open shift to close.'" />
      <AppButton variant="secondary" icon="clock" @click="router.replace({ name: 'shift' })">Back to shift</AppButton>
    </div>

    <StickyBar v-if="summary">
      <AppButton size="lg" block icon="check-circle" :loading="submitting" @click="submit">
        {{ submitting ? 'Closing…' : 'Close shift' }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { useConfirm } from '../composables/useConfirm';
import { money, qty, plural, shortDate, longDate } from '../utils/format';
import type { ShiftClosingSummary, PaymentReconciliationRow, VarianceStatus } from '../types';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, KpiTile, FormField, BaseInput, BaseTextarea, SkeletonList, StickyBar } from '../components/ui';

const store = useSessionStore();
const shift = useShiftStore();
const router = useRouter();
const route = useRoute();
const toast = useToast();
const { confirm } = useConfirm();
const currency = computed(() => store.currencyDisplay);

const loading = ref(true);
const submitting = ref(false);
const error = ref('');
const summary = ref<ShiftClosingSummary | null>(null);
const rows = ref<PaymentReconciliationRow[]>([]);
const notes = ref('');

const diff = (row: PaymentReconciliationRow) => (Number(row.closing_amount) || 0) - (row.expected_amount ?? 0);
const netDifference = computed(() => rows.value.reduce((sum, r) => sum + diff(r), 0));
// Mirrors shift closing's variance_status (flag only; closing is never blocked).
const varianceStatus = computed<VarianceStatus>(() => {
  const d = Math.abs(netDifference.value);
  if (d < 0.005) return 'Balanced';
  return d <= (summary.value?.variance_tolerance || 0) + 0.005 ? 'Within Tolerance' : 'Exceeds Tolerance';
});
const outsideCount = computed(() => {
  const o = summary.value?.outside_window;
  return o ? o.orders_count + o.payments_count : 0;
});
const outsideText = computed(() => {
  const o = summary.value!.outside_window;
  const parts: string[] = [];
  if (o.orders_count) parts.push(`${plural(o.orders_count, 'order')} (${currency.value} ${money(o.orders_total)})`);
  if (o.payments_count) parts.push(`${plural(o.payments_count, 'payment')} (${currency.value} ${money(o.payments_total)})`);
  return parts.join(' and ') + (o.orders_count + o.payments_count === 1 ? ' was made' : ' were made');
});
const isOwnShift = computed(() => !summary.value || summary.value.driver === store.session?.user);
const closingTitle = computed(() => {
  const s = summary.value!;
  const who = isOwnShift.value ? 'Your' : `${s.driver_name}'s`;
  return s.is_stale ? `${who} shift from ${shortDate(s.shift_date)} is still open` : `Closing ${s.driver_name}'s shift`;
});

const load = async () => {
  try {
    // ?opening= lets a manager close a specific driver's shift (from the fleet dashboard).
    summary.value = await api.getShiftClosingSummary((route.query.opening as string) || undefined);
    rows.value = summary.value.payment_reconciliation.map((r) => ({ ...r }));
  } catch (e: any) {
    error.value = e?.message || 'No open shift to close.';
  } finally {
    loading.value = false;
  }
};

const submit = async () => {
  if (!summary.value) return;
  if (!summary.value.blind && varianceStatus.value === 'Exceeds Tolerance') {
    const ok = await confirm({
      title: 'Close with a variance?',
      message: `The count is ${netDifference.value > 0 ? 'over' : 'short'} by ${currency.value} ${money(Math.abs(netDifference.value))}, beyond the tolerance. Your manager will see this closing flagged.`,
      confirmLabel: 'Close anyway',
      tone: 'warning',
    });
    if (!ok) return;
  }
  submitting.value = true;
  error.value = '';
  try {
    const payload: PaymentReconciliationRow[] = rows.value.map((r) => ({ ...r, closing_amount: Number(r.closing_amount) || 0 }));
    const closed = await api.closeShift(summary.value.opening_shift, payload, notes.value);
    await shift.refresh(true);
    toast.success('Shift closed', { message: varianceStatus.value === 'Balanced' ? 'The drawer balanced.' : `Net variance ${currency.value} ${money(Math.abs(netDifference.value))}.` });
    router.replace({ name: 'closing-report', params: { name: closed.name } });
  } catch (e: any) {
    error.value = e?.message || 'Failed to close shift';
  } finally {
    submitting.value = false;
  }
};

onMounted(load);
</script>
