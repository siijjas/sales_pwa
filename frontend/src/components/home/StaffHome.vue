<template>
  <WorkspacePage :eyebrow="store.workspaceLabel" :title="`${greeting}${store.firstName ? `, ${store.firstName}` : ''}`">
    <template #actions>
      <button
        v-if="shift.usesShifts"
        type="button"
        class="focus-ring flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] font-bold"
        :class="shiftChip.class"
        @click="router.push({ name: 'shift' })"
      >
        <span class="h-2 w-2 rounded-full bg-current" />
        {{ shiftChip.label }}
      </button>
    </template>

    <div class="space-y-6">
      <AppAlert v-if="setupMessage" tone="warning" :message="setupMessage" />

      <!-- Shift gate: the one thing to do before anything else -->
      <AppCard v-if="shiftNotice" padding="lg" class="ring-1 ring-inset ring-warning/30">
        <div class="flex items-start gap-3.5">
          <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-warning/16 text-warning"><AppIcon name="clock" :size="22" /></span>
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-bold text-foreground">{{ shiftNotice.title }}</p>
            <p class="mt-0.5 text-[13px] leading-relaxed text-muted">{{ shiftNotice.body }}</p>
            <AppButton class="mt-3" size="sm" :icon="shift.isStale ? 'check-circle' : 'play-circle'" @click="router.push(shift.gateRoute)">
              {{ shift.isStale ? 'Close that shift' : 'Open shift' }}
            </AppButton>
          </div>
        </div>
      </AppCard>

      <!-- Primary: sell -->
      <section>
        <button
          type="button"
          class="focus-ring flex w-full items-center gap-4 rounded-3xl bg-primary p-4 text-left text-primary-fg shadow-btn transition active:scale-[0.99]"
          :class="shift.needsShift ? 'opacity-60' : ''"
          @click="startSale"
        >
          <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/15"><AppIcon name="cart" :size="24" /></span>
          <span class="min-w-0 flex-1">
            <span class="block text-[17px] font-bold leading-tight">New sale</span>
            <span class="block text-[12.5px] opacity-80">{{ caps.can_invoice ? 'Order, invoice and collect in one go' : 'Take an order for the back office' }}</span>
          </span>
          <AppIcon name="arrow-right" :size="20" />
        </button>
        <AppCard v-if="sale.hasDraft" padding="none" class="mt-2.5">
          <ListRow interactive chevron icon="edit" tone="warning" title="Resume sale in progress" :subtitle="draftSubtitle" @click="router.push({ name: sale.lines.length ? 'sell-review' : 'sell-items' })">
            <template #trailing>
              <button type="button" class="rounded-full px-2 py-1 text-[12px] font-semibold text-danger" @click.stop="discardDraft">Discard</button>
            </template>
          </ListRow>
        </AppCard>
      </section>

      <!-- Shortcuts -->
      <section>
        <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <ActionTile label="Collect payment" icon="wallet" tone="success" hint="Against invoices" @click="go({ name: 'customers' }, true)" />
          <ActionTile v-if="caps.can_return" label="Return" icon="rotate-ccw" tone="danger" hint="Credit note" @click="go({ name: 'customers' }, true)" />
          <ActionTile v-if="canLoadStock" label="Load van" icon="truck" tone="warning" hint="From main warehouse" :to="{ name: 'stock-load' }" />
          <ActionTile v-if="caps.uses_shifts" label="Cash out" icon="banknote" tone="info" hint="Expense or deposit" @click="go({ name: 'shift-cash' }, true)" />
          <ActionTile v-if="!caps.uses_shifts && store.showsCustomerBalance" label="Ledger" icon="ledger" tone="info" hint="Customer statement" :to="{ name: 'customers' }" />
          <ActionTile v-if="store.isManager" label="Fleet" icon="activity" tone="primary" hint="Today across staff" :to="{ name: 'reports' }" />
        </div>
      </section>

      <!-- This shift -->
      <section v-if="shiftSummary">
        <SectionHeader title="This shift" :description="shiftSince ? `Open since ${shiftSince}` : undefined" action-label="Summary" @action="router.push({ name: 'shift-summary' })" />
        <div class="grid grid-cols-3 gap-2.5">
          <KpiTile label="Sales" :value="money(shiftSummary.totals.total_sales)" :sub="plural(shiftSummary.totals.sales_orders_count, 'order')" tone="primary" />
          <KpiTile label="Collected" :value="money(shiftSummary.totals.total_collections)" :sub="plural(shiftSummary.totals.payments_count, 'payment')" tone="success" />
          <KpiTile label="Cash in hand" :value="money(shiftSummary.totals.expected_cash)" :sub="shiftSummary.draft_orders.length ? `${plural(shiftSummary.draft_orders.length, 'draft')} pending` : `Float ${money(shiftSummary.totals.total_opening_float)}`" tone="info" />
        </div>
      </section>

      <!-- Today -->
      <section>
        <SectionHeader title="Today" action-label="Activity" @action="router.push({ name: 'activity' })" />
        <div class="grid grid-cols-2 gap-2.5">
          <KpiTile label="Orders" :value="dailySummary?.sales_orders.count || 0" :sub="`${currency} ${money(dailySummary?.sales_orders.total)}`" icon="cart" tone="primary" interactive @click="router.push({ name: 'activity', query: { tab: 'orders' } })" />
          <KpiTile label="Collected" :value="dailySummary?.payments.count || 0" :sub="`${currency} ${money(dailySummary?.payments.total)}`" icon="wallet" tone="success" interactive @click="router.push({ name: 'activity', query: { tab: 'payments' } })" />
        </div>
      </section>

      <!-- Recent -->
      <section>
        <SectionHeader title="Recent orders" />
        <SkeletonList v-if="loading" :rows="3" height="4rem" />
        <EmptyState v-else-if="!orders.length" icon="receipt" title="No orders yet" description="Orders you create show up here." />
        <AppCard v-else padding="none" class="divide-y divide-line">
          <ListRow v-for="order in orders" :key="order.name" interactive chevron :title="order.customer_name" :subtitle="`${order.name} · ${relativeDate(order.transaction_date)}`" @click="router.push({ name: 'order', params: { name: order.name } })">
            <template #leading><Avatar :name="order.customer_name" size="sm" tone="neutral" /></template>
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(order.grand_total) }}</p>
                <StatusBadge class="mt-0.5" :status="order.status" :dot="false" />
              </div>
            </template>
          </ListRow>
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router';
import * as api from '../../api/frappe';
import type { SalesOrder, ShiftReport } from '../../types';
import { useSessionStore } from '../../stores/session';
import { useSaleStore } from '../../stores/sale';
import { useShiftStore } from '../../stores/shift';
import { useConfirm } from '../../composables/useConfirm';
import { money, plural, relativeDate, time, shortDate } from '../../utils/format';
import WorkspacePage from '../WorkspacePage.vue';
import { AppCard, AppAlert, AppButton, AppIcon, ActionTile, Avatar, KpiTile, ListRow, SectionHeader, SkeletonList, EmptyState, StatusBadge } from '../ui';

const store = useSessionStore();
const sale = useSaleStore();
const shift = useShiftStore();
const router = useRouter();
const route = useRoute();
const { confirm } = useConfirm();

const caps = computed(() => store.capabilities);
const currency = computed(() => store.currencyDisplay);
const canLoadStock = computed(() => (store.driverConfig ? caps.value.can_load_stock : store.isManager));

const greeting = computed(() => {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
});

const setupMessage = computed(() => {
  if (store.driverConfig || route.query.setup !== 'driver-profile') return '';
  return store.isManager
    ? 'Create and activate a sales profile before opening stock tools.'
    : 'Your account has no active sales profile yet. Ask a manager to assign one before using stock tools.';
});

const shiftChip = computed(() => {
  if (shift.isStale) return { label: `Unclosed · ${shortDate(shift.active!.shift_date)}`, class: 'bg-warning/16 text-warning' };
  if (shift.isOpen) return { label: 'Shift open', class: 'bg-success/14 text-success' };
  return { label: 'No shift', class: 'bg-card-muted text-muted' };
});
const shiftSince = computed(() => (shift.active?.period_start ? time(shift.active.period_start) : ''));

// A shift left open from an earlier day has to be closed first; with the profile's
// require_open_shift, selling also waits for today's shift. The server enforces the
// same rule — this just gets the driver there sooner.
const shiftNotice = computed(() => {
  if (loading.value || !shift.usesShifts) return null;
  if (shift.isStale) {
    return {
      title: `Your shift from ${shortDate(shift.active!.shift_date)} was never closed`,
      body: caps.value.requires_open_shift ? "Close it, then open today's shift to start selling." : "Close it so that day's cash is reconciled. A new shift can't open until you do.",
    };
  }
  if (caps.value.requires_open_shift && !shift.active) {
    return { title: 'Open your shift to start selling', body: 'Orders, payments, returns and expenses need an open shift.' };
  }
  return null;
});

function go(to: RouteLocationRaw, gated = false) {
  if (gated && shift.needsShift) return router.push(shift.gateRoute);
  return router.push(to);
}
function startSale() {
  if (shift.needsShift) return router.push(shift.gateRoute);
  if (sale.hasDraft) return router.push({ name: sale.lines.length ? 'sell-review' : 'sell-items' });
  return router.push({ name: 'sell-customer' });
}
const draftSubtitle = computed(() => {
  const who = sale.customer?.customer_name || 'No customer yet';
  return sale.lines.length ? `${who} · ${plural(sale.lines.length, 'item')} · ${currency.value} ${money(sale.subtotal)}` : who;
});
async function discardDraft() {
  if (await confirm({ title: 'Discard this sale?', message: 'The items added so far will be removed.', confirmLabel: 'Discard', tone: 'danger', icon: 'trash' })) {
    sale.reset();
  }
}

const orders = ref<SalesOrder[]>([]);
const dailySummary = ref<{ sales_orders: { count: number; total: number }; payments: { count: number; total: number } } | null>(null);
const shiftSummary = ref<ShiftReport | null>(null);
const loading = ref(true);

onMounted(async () => {
  if (!store.session) return;
  try {
    const [ordersData, summaryData] = await Promise.all([
      api.recentOrders(store.session.user, { pageLength: 5 }),
      api.getDailySummary(),
      shift.refresh(true),
    ]);
    orders.value = ordersData;
    dailySummary.value = summaryData;
  } finally {
    loading.value = false;
  }
  if (shift.isOpen) {
    shiftSummary.value = await api.getShiftSummary().catch(() => null);
  }
});
</script>
