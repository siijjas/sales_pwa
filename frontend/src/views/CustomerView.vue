<template>
  <WorkspacePage back :title="customer?.customer_name || 'Customer'" :subtitle="customer ? [customer.name, customer.territory].filter(Boolean).join(' · ') : undefined">
    <template #actions>
      <AppButton variant="ghost" size="sm" icon="refresh" :loading="loading" aria-label="Refresh" @click="load" />
    </template>

    <SkeletonList v-if="loading && !customer" :rows="3" height="6rem" />
    <AppAlert v-else-if="error" tone="danger" :message="error" />

    <div v-else-if="customer" class="space-y-5">
      <!-- Identity -->
      <AppCard padding="sm">
        <div class="flex items-center gap-3">
          <Avatar :name="customer.customer_name" size="lg" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-[16px] font-bold text-foreground">{{ customer.customer_name }}</p>
            <p class="truncate text-xs text-muted">{{ customer.name }}</p>
            <a v-if="customer.mobile_no" :href="`tel:${customer.mobile_no}`" class="tnum mt-1 inline-flex items-center gap-1 text-[13px] font-semibold text-primary">
              {{ customer.mobile_no }}
            </a>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1.5">
            <StatusBadge v-if="customer.customer_group" tone="neutral" :dot="false">{{ customer.customer_group }}</StatusBadge>
            <StatusBadge v-if="customer.territory" tone="info" :dot="false">{{ customer.territory }}</StatusBadge>
          </div>
        </div>
      </AppCard>

      <!-- Balance -->
      <AppCard v-if="store.showsCustomerBalance" padding="lg" class="ring-1 ring-inset ring-primary/20">
        <p class="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">Outstanding balance</p>
        <p v-if="summary" class="tnum mt-1 text-[30px] font-semibold leading-none tracking-tightest text-foreground">
          {{ currency }} {{ money(summary.outstanding_balance) }}
        </p>
        <div v-else class="skeleton mt-2 h-8 w-40" />
        <div v-if="summary && (summary.last_invoice || summary.last_payment)" class="mt-4 space-y-2 border-t border-line pt-3">
          <DataRow v-if="summary.last_invoice" :label="`Last invoice · ${shortDate(summary.last_invoice.posting_date)}`" :value="`${currency} ${money(summary.last_invoice.grand_total)}`" />
          <DataRow v-if="summary.last_payment" :label="`Last payment · ${shortDate(summary.last_payment.posting_date)}`" :value="`${currency} ${money(summary.last_payment.paid_amount)}`" />
        </div>
      </AppCard>

      <!-- Actions -->
      <div class="grid grid-cols-2 gap-2.5">
        <ActionTile label="New sale" icon="cart" tone="primary" hint="Order for this customer" @click="startSale" />
        <ActionTile label="Collect payment" icon="wallet" tone="success" hint="Against invoices" @click="gated({ name: 'collect', params: { name: customer.name } })" />
        <ActionTile v-if="caps.can_return" label="Return" icon="rotate-ccw" tone="danger" hint="Issue a credit note" @click="gated({ name: 'return-items', params: { name: customer.name } })" />
        <ActionTile v-if="store.showsCustomerBalance" label="Ledger" icon="ledger" tone="info" hint="Statement of account" :to="{ name: 'ledger', params: { name: customer.name } }" />
      </div>

      <!-- Outstanding invoices -->
      <section v-if="store.showsCustomerBalance">
        <SectionHeader title="Outstanding invoices" :description="invoices.length ? `${plural(invoices.length, 'invoice')} · ${currency} ${money(outstandingTotal)}` : undefined" />
        <SkeletonList v-if="invoicesLoading" :rows="2" height="3.5rem" />
        <EmptyState v-else-if="!invoices.length" icon="file-text" title="Nothing outstanding" description="This customer has no unpaid invoices." />
        <AppCard v-else padding="none" class="divide-y divide-line">
          <ListRow v-for="inv in invoices" :key="inv.name" dense icon="file-text" tone="warning" :title="inv.name" :subtitle="shortDate(inv.posting_date)">
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(inv.outstanding_amount) }}</p>
                <p v-if="inv.outstanding_amount < inv.grand_total - 0.005" class="tnum text-[11px] text-muted">of {{ money(inv.grand_total) }}</p>
              </div>
              <AppButton variant="ghost" size="sm" icon="printer" :aria-label="`Print ${inv.name}`" @click="api.downloadPdf('Sales Invoice', inv.name)" />
            </template>
          </ListRow>
        </AppCard>
      </section>

      <!-- Recent orders -->
      <section>
        <SectionHeader title="Recent orders" action-label="See all" @action="router.push({ name: 'activity', query: { tab: 'orders', customer: customer.name } })" />
        <SkeletonList v-if="ordersLoading" :rows="3" height="4rem" />
        <EmptyState v-else-if="!orders.length" icon="receipt" title="No orders yet" description="Orders you create for this customer show up here." />
        <AppCard v-else padding="none" class="divide-y divide-line">
          <ListRow v-for="o in orders" :key="o.name" interactive chevron :title="o.name" :subtitle="relativeDate(o.transaction_date)" @click="router.push({ name: 'order', params: { name: o.name } })">
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(o.grand_total) }}</p>
                <StatusBadge class="mt-0.5" :status="o.status" :dot="false" />
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
import * as api from '../api/frappe';
import type { Customer, CustomerSummary, OutstandingInvoice, SalesOrder } from '../types';
import { useSessionStore } from '../stores/session';
import { useSaleStore } from '../stores/sale';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { money, plural, relativeDate, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, ActionTile, Avatar, DataRow, ListRow, SectionHeader, StatusBadge, SkeletonList, EmptyState } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const sale = useSaleStore();
const shift = useShiftStore();
const toast = useToast();

const name = computed(() => String(route.params.name));
const caps = computed(() => store.capabilities);
const currency = computed(() => store.currencyDisplay);

const customer = ref<Customer | null>(null);
const summary = ref<CustomerSummary | null>(null);
const invoices = ref<OutstandingInvoice[]>([]);
const orders = ref<SalesOrder[]>([]);
const loading = ref(true);
const invoicesLoading = ref(false);
const ordersLoading = ref(false);
const error = ref('');

const outstandingTotal = computed(() => invoices.value.reduce((sum, i) => sum + (i.outstanding_amount || 0), 0));

async function load() {
  loading.value = true;
  error.value = '';
  try {
    customer.value = await api.getCustomer(name.value);
  } catch (e: any) {
    error.value = e?.message || 'Customer not found';
    loading.value = false;
    return;
  }
  loading.value = false;

  const tasks: Promise<unknown>[] = [];
  if (store.showsCustomerBalance) {
    summary.value = null;
    tasks.push(api.getCustomerSummary(name.value).then((s) => (summary.value = s)).catch(() => (summary.value = { outstanding_balance: 0 })));
    invoicesLoading.value = true;
    tasks.push(
      api
        .getOutstandingInvoices(name.value)
        .then((rows) => (invoices.value = rows))
        .catch(() => (invoices.value = []))
        .finally(() => (invoicesLoading.value = false)),
    );
  }
  if (store.session) {
    ordersLoading.value = true;
    tasks.push(
      api
        .recentOrders(store.session.user, { customer: name.value, pageLength: 5 })
        .then((rows) => (orders.value = rows))
        .catch(() => (orders.value = []))
        .finally(() => (ordersLoading.value = false)),
    );
  }
  await Promise.all(tasks);
}

onMounted(() => {
  shift.refresh();
  load();
});

// Actions that need an open shift send the driver there first; the server enforces the same.
function gated(to: RouteLocationRaw) {
  if (shift.needsShift) {
    toast.warning(shift.isStale ? 'Close your previous shift first' : 'Open your shift first', { message: 'Sales, payments and returns need an open shift.' });
    return router.push(shift.gateRoute);
  }
  return router.push(to);
}

function startSale() {
  if (!customer.value) return;
  if (shift.needsShift) return gated({ name: 'sell-items' });
  sale.setCustomer(customer.value);
  return router.push({ name: 'sell-items' });
}
</script>
