<template>
  <WorkspacePage back :title="order ? order.name : 'Order'" :subtitle="order?.customer_name || ''">
    <template #actions>
      <button type="button" class="focus-ring flex h-10 w-10 items-center justify-center rounded-full text-muted transition hover:bg-card-muted hover:text-foreground" aria-label="Refresh" @click="load">
        <AppIcon name="refresh" :size="18" :class="loading ? 'animate-spin' : ''" />
      </button>
    </template>

    <SkeletonList v-if="loading && !order" :rows="3" height="6rem" />
    <AppAlert v-else-if="error && !order" tone="danger" :message="error" />

    <div v-else-if="order" class="space-y-4 pb-28">
      <AppAlert v-if="deferredNote" tone="warning" title="Some items are pending delivery" :message="deferredNote" />
      <AppAlert v-if="deliveredNote" tone="success" :message="deliveredNote" />
      <AppAlert v-if="error" tone="danger" :message="error" />

      <!-- Status + customer -->
      <AppCard padding="none">
        <div class="flex flex-wrap items-center gap-2 px-4 pt-4">
          <StatusBadge :status="order.status" />
          <StatusBadge :tone="docTone(order.docstatus)" :dot="false">{{ docLabel(order.docstatus) }}</StatusBadge>
          <StatusBadge v-if="order.docstatus === 1" :tone="billedTone" :dot="false">{{ billedLabel }}</StatusBadge>
          <span class="ml-auto text-xs text-muted">{{ shortDate(order.transaction_date) }}</span>
        </div>
        <ListRow interactive chevron :title="order.customer_name" :subtitle="order.customer" @click="router.push({ name: 'customer', params: { name: order.customer } })">
          <template #leading><Avatar :name="order.customer_name" /></template>
        </ListRow>
      </AppCard>

      <!-- Items -->
      <AppCard padding="none">
        <div class="border-b border-line px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted">Items ({{ order.items.length }})</div>
        <div class="divide-y divide-line">
          <div v-for="line in order.items" :key="line.item_code" class="flex items-start justify-between gap-3 px-4 py-3">
            <div class="min-w-0">
              <p class="font-semibold text-foreground">{{ line.item_name }}</p>
              <p class="text-xs text-muted">{{ line.item_code }}<span v-if="line.stock_uom"> · {{ line.stock_uom }}</span></p>
            </div>
            <div class="shrink-0 text-right">
              <p class="tnum text-sm font-bold text-foreground">{{ currency }} {{ money(line.amount) }}</p>
              <p class="tnum text-xs text-muted">{{ qty(line.qty) }} × {{ currency }} {{ money(line.rate) }}</p>
            </div>
          </div>
        </div>
        <div class="space-y-2 border-t border-line px-4 py-3">
          <DataRow v-if="order.discount_amount" label="Discount" :value="`− ${currency} ${money(order.discount_amount)}`" />
          <DataRow v-if="order.total_taxes_and_charges" label="Tax" :value="`${currency} ${money(order.total_taxes_and_charges)}`" />
          <DataRow label="Grand total" :value="`${currency} ${money(order.grand_total)}`" emphasis />
        </div>
      </AppCard>

      <!-- Invoices raised from this order -->
      <AppCard v-if="invoices.length" padding="none">
        <div class="border-b border-line px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted">Invoices ({{ invoices.length }})</div>
        <div class="divide-y divide-line">
          <ListRow
            v-for="inv in invoices"
            :key="inv.name"
            dense
            icon="file-text"
            :tone="inv.is_return ? 'danger' : inv.outstanding_amount > 0.005 ? 'warning' : 'success'"
            :title="inv.name"
            :subtitle="`${inv.is_return ? 'Credit note' : inv.status} · ${shortDate(inv.posting_date)}`"
          >
            <template #trailing>
              <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(Math.abs(inv.grand_total)) }}</p>
              <AppButton variant="ghost" size="sm" icon="printer" :aria-label="`Print ${inv.name}`" @click="print('Sales Invoice', inv.name)" />
            </template>
          </ListRow>
        </div>
      </AppCard>

      <AppAlert
        v-if="!canInvoice && order.docstatus === 1 && !fullyBilled"
        tone="info"
        message="This order is submitted. Invoicing and delivery are handled by the back office."
      />

      <!-- Secondary actions -->
      <div class="flex flex-wrap gap-2">
        <AppButton v-if="order.docstatus === 1" variant="secondary" size="sm" icon="printer" @click="printPdf">Print</AppButton>
        <AppButton variant="secondary" size="sm" icon="wallet" @click="router.push({ name: 'collect', params: { name: order.customer } })">Collect payment</AppButton>
      </div>
    </div>

    <!-- Primary action -->
    <StickyBar v-if="order && order.docstatus === 0">
      <div class="grid grid-cols-2 gap-2">
        <AppButton variant="secondary" size="lg" block icon="edit" :disabled="submitting" @click="editOrder">Edit</AppButton>
        <AppButton size="lg" block icon="check" :loading="submitting" @click="submitOrder">Submit order</AppButton>
      </div>
    </StickyBar>
    <StickyBar v-else-if="order && canInvoice && order.docstatus === 1 && !fullyBilled">
      <AppButton size="lg" block icon="file-text" @click="invoiceOpen = true">Create invoice</AppButton>
    </StickyBar>
    <StickyBar v-else-if="order && canDeliver && hasPendingDelivery">
      <AppButton size="lg" block icon="truck" :loading="delivering" @click="deliverPending">Deliver pending items</AppButton>
    </StickyBar>

    <InvoiceSheet v-if="order" v-model="invoiceOpen" :order="order" @created="onInvoiceCreated" />
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { OrderInvoice, SalesOrder } from '../types';
import { useSessionStore } from '../stores/session';
import { useSaleStore } from '../stores/sale';
import { useToast } from '../composables/useToast';
import { usePrint } from '../composables/usePrint';
import { money, qty, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import InvoiceSheet from '../components/InvoiceSheet.vue';
import { AppCard, AppButton, AppAlert, AppIcon, Avatar, DataRow, ListRow, SkeletonList, StatusBadge, StickyBar } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const sale = useSaleStore();
const toast = useToast();
const { print } = usePrint();

const orderId = route.params.name as string;
const currency = computed(() => store.currencyDisplay);
const canInvoice = computed(() => store.capabilities.can_invoice);
const canDeliver = computed(() => store.capabilities.can_deliver);

const order = ref<SalesOrder | null>(null);
const invoices = ref<OrderInvoice[]>([]);
const loading = ref(true);
const error = ref('');
const submitting = ref(false);
const delivering = ref(false);
const invoiceOpen = ref(false);
const deferredNote = ref('');
const deliveredNote = ref('');

const fullyBilled = computed(() => (order.value?.per_billed ?? 0) >= 100);
const billedLabel = computed(() => {
  const p = order.value?.per_billed ?? 0;
  return p >= 100 ? 'Invoiced' : p > 0 ? 'Partly invoiced' : 'Not invoiced';
});
const billedTone = computed<'success' | 'warning' | 'neutral'>(() => {
  const p = order.value?.per_billed ?? 0;
  return p >= 100 ? 'success' : p > 0 ? 'warning' : 'neutral';
});
// Billed in full but not yet delivered in full: sold while short of van stock.
const hasPendingDelivery = computed(
  () => !!order.value && order.value.docstatus === 1 && fullyBilled.value
    && (order.value.per_delivered ?? 100) < 100 && order.value.status !== 'Closed',
);

const docLabel = (d: number) => (d === 0 ? 'Draft' : d === 1 ? 'Submitted' : d === 2 ? 'Cancelled' : 'Unknown');
const docTone = (d: number): 'success' | 'danger' | 'warning' => (d === 1 ? 'success' : d === 2 ? 'danger' : 'warning');

async function load() {
  loading.value = true;
  error.value = '';
  try {
    order.value = await api.getSalesOrder(orderId);
    // Only a submitted order can carry invoices; a failed lookup just hides the card.
    invoices.value = order.value.docstatus === 1 && (order.value.per_billed ?? 0) > 0
      ? await api.getOrderInvoices(orderId).catch(() => [])
      : [];
  } catch (e: any) {
    error.value = e?.message || 'Failed to load order';
  } finally {
    loading.value = false;
  }
}
onMounted(load);

async function submitOrder() {
  if (!order.value || order.value.docstatus !== 0) return;
  submitting.value = true;
  error.value = '';
  try {
    await api.submitSalesOrder(order.value.name);
    toast.success(`Order ${order.value.name} submitted`);
    await load();
  } catch (e: any) {
    error.value = e?.message || 'Failed to submit order';
  } finally {
    submitting.value = false;
  }
}

function editOrder() {
  if (!order.value) return;
  sale.loadOrder(
    order.value.name,
    { name: order.value.customer, customer_name: order.value.customer_name, customer_group: '', territory: '' },
    order.value.items || [],
    { percent: order.value.additional_discount_percentage || 0, amount: order.value.discount_amount || 0 },
  );
  router.push({ name: 'sell-review' });
}

async function onInvoiceCreated(invoiceName: string, note: string) {
  invoiceOpen.value = false;
  deferredNote.value = note;
  toast.success(`Invoice ${invoiceName} created`, { action: { label: 'Print', run: () => print('Sales Invoice', invoiceName) }, duration: 8000 });
  await load();
}

async function deliverPending() {
  if (!order.value) return;
  delivering.value = true;
  error.value = '';
  try {
    const notes = await api.deliverPendingItems(order.value.name);
    deliveredNote.value = `Delivered from van: ${notes.join(', ')}`;
    deferredNote.value = '';
    toast.success('Pending items delivered');
    await load();
  } catch (e: any) {
    error.value = e?.message || 'Failed to deliver pending items';
  } finally {
    delivering.value = false;
  }
}

const printPdf = () => print('Sales Order', orderId);
</script>
