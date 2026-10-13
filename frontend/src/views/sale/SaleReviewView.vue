<template>
  <WorkspacePage :back="{ name: 'sell-items' }" title="Review" :subtitle="sale.orderName ? `Editing draft ${sale.orderName}` : 'Check items and totals before confirming'">
    <template #actions>
      <AppButton v-if="sale.lines.length" variant="ghost" size="sm" icon="trash" @click="clear">Clear</AppButton>
    </template>
    <template #sticky>
      <StepHeader :steps="STEPS" :current="2" />
    </template>

    <div class="space-y-4 pb-36">
      <!-- Customer -->
      <AppCard v-if="customer" padding="none">
        <ListRow interactive chevron :title="customer.customer_name" :subtitle="customer.name" @click="router.push({ name: 'sell-customer' })">
          <template #leading><Avatar :name="customer.customer_name" /></template>
        </ListRow>
      </AppCard>

      <!-- Items -->
      <AppCard padding="none">
        <div class="flex items-center justify-between border-b border-line px-4 py-3">
          <span class="text-xs font-bold uppercase tracking-wider text-muted">Items ({{ sale.lines.length }})</span>
          <button type="button" class="text-[13px] font-semibold text-primary" @click="router.push({ name: 'sell-items' })">Add more</button>
        </div>
        <div class="divide-y divide-line">
          <div v-for="line in sale.lines" :key="line.item.item_code" class="flex items-center justify-between gap-3 p-4">
            <div class="min-w-0 flex-1">
              <p class="font-semibold leading-tight text-foreground">{{ line.item.item_name }}</p>
              <p class="mt-0.5 text-xs text-muted">{{ line.item.item_code }}</p>
              <button
                type="button"
                class="mt-2 inline-flex w-fit items-center gap-1.5 rounded-xl bg-card-muted px-2.5 py-1.5 text-xs font-semibold ring-1 ring-inset ring-line transition"
                :class="store.allowRateChange ? 'text-foreground hover:ring-primary' : 'cursor-default text-muted opacity-70'"
                @click="openEdit(line)"
              >
                <span class="tnum">{{ currency }} {{ money(lineRate(line)) }}</span>
                <span class="text-subtle">/ {{ line.item.stock_uom }}</span>
                <AppIcon v-if="store.allowRateChange" name="edit" :size="13" class="ml-0.5 text-primary" />
              </button>
              <p class="tnum mt-1.5 text-sm font-bold text-foreground">{{ currency }} {{ money(line.qty * lineRate(line)) }}</p>
            </div>
            <QtyStepper :model-value="line.qty" @change="(d: number) => sale.changeQty(line.item.item_code, d)" />
          </div>
        </div>
      </AppCard>

      <!-- Totals -->
      <AppCard>
        <div class="space-y-2.5">
          <DataRow label="Subtotal" :value="`${currency} ${money(net)}`" />
          <div v-if="store.allowDiscountChange" class="space-y-2">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-muted">Discount<span v-if="store.maxDiscountPercent" class="ml-1 text-xs text-subtle">· up to {{ store.maxDiscountPercent }}%</span></span>
              <SegmentedControl
                :model-value="sale.discountMode"
                :options="[{ value: 'percent', label: '%' }, { value: 'amount', label: currency }]"
                class="w-[120px]"
                @update:model-value="(v: string) => sale.setDiscount(v as DiscountMode, 0)"
              />
            </div>
            <div class="flex items-center justify-between gap-3 text-sm text-muted">
              <span>{{ sale.discountMode === 'percent' ? 'Discount %' : `Discount (${currency})` }}</span>
              <input
                v-if="sale.discountMode === 'percent'"
                :value="sale.discountPercent || ''"
                type="number"
                inputmode="decimal"
                min="0"
                :max="store.maxDiscountPercent || 100"
                step="0.01"
                placeholder="0"
                class="field-inline"
                @input="sale.setDiscount('percent', Number(($event.target as HTMLInputElement).value) || 0)"
              />
              <input
                v-else
                :value="sale.discountAmount || ''"
                type="number"
                inputmode="decimal"
                min="0"
                :max="net"
                step="0.01"
                placeholder="0.00"
                class="field-inline"
                @input="sale.setDiscount('amount', Number(($event.target as HTMLInputElement).value) || 0)"
              />
            </div>
          </div>
          <DataRow v-if="discountAmount > 0" label="Discount" :value="`− ${currency} ${money(discountAmount)}`" />
          <DataRow v-if="tax" label="Tax" :value="`${currency} ${money(tax)}`" />
          <DataRow label="Total" :value="`${currency} ${money(grand)}`" emphasis />
        </div>
      </AppCard>

      <AppAlert v-if="submitError" tone="danger" :message="submitError" />
    </div>

    <StickyBar>
      <div class="grid gap-2" :class="caps.can_invoice ? 'grid-cols-2' : ''">
        <AppButton :variant="caps.can_invoice ? 'secondary' : 'primary'" size="lg" block :loading="submitting === 'order'" :disabled="!!submitting || !customer" icon="check" @click="submit(false)">
          Submit order
        </AppButton>
        <AppButton v-if="caps.can_invoice" size="lg" block :loading="submitting === 'invoice'" :disabled="!!submitting || !customer" icon="file-text" @click="submit(true)">
          Submit & invoice
        </AppButton>
      </div>
    </StickyBar>

    <!-- Edit price -->
    <BottomSheet v-model="sheetOpen" title="Edit unit price" :subtitle="editingLine?.item.item_name">
      <FormField :label="`Price per ${editingLine?.item.stock_uom || 'unit'} (${currency})`">
        <BaseInput v-model="editPrice" type="number" inputmode="decimal" :prefix="currency" @keyup.enter="savePrice" />
      </FormField>
      <template #footer>
        <div class="grid grid-cols-2 gap-2.5">
          <AppButton variant="subtle" size="lg" block @click="sheetOpen = false">Cancel</AppButton>
          <AppButton size="lg" block @click="savePrice">Apply</AppButton>
        </div>
      </template>
    </BottomSheet>

    <InvoiceSheet v-if="submittedOrder" v-model="invoiceOpen" :order="submittedOrder" @created="onInvoiceCreated" />
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import type { CartLine, SalesOrder } from '../../types';
import { useSessionStore } from '../../stores/session';
import { useSaleStore, lineRate, type DiscountMode } from '../../stores/sale';
import { useToast } from '../../composables/useToast';
import { useConfirm } from '../../composables/useConfirm';
import { money, isoToday } from '../../utils/format';
import WorkspacePage from '../../components/WorkspacePage.vue';
import InvoiceSheet from '../../components/InvoiceSheet.vue';
import { AppCard, AppAlert, AppButton, AppIcon, Avatar, BaseInput, BottomSheet, DataRow, FormField, ListRow, QtyStepper, SegmentedControl, StepHeader, StickyBar } from '../../components/ui';

const STEPS = ['Customer', 'Items', 'Review'];

const store = useSessionStore();
const sale = useSaleStore();
const router = useRouter();
const toast = useToast();
const { confirm } = useConfirm();

const caps = computed(() => store.capabilities);
const customer = computed(() => sale.customer);
const currency = computed(() => store.currencyDisplay);
const net = computed(() => sale.subtotal);
const orderDetail = ref<SalesOrder | null>(null);
const tax = computed(() => {
  const t = orderDetail.value?.total_taxes_and_charges;
  return t && t > 0 ? t : 0;
});
// The server sets apply_discount_on = "Grand Total" (Sales Profile default), so ERPNext
// applies a percentage to net + tax, not to net alone. Mirror that here or the figure
// quoted to the customer differs from the order that gets saved whenever tax applies.
const applyDiscountOnGrandTotal = computed(() => (store.driverConfig?.apply_discount_on || 'Grand Total') === 'Grand Total');
const discountBase = computed(() => (applyDiscountOnGrandTotal.value ? net.value + tax.value : net.value));
const effectiveDiscountPercent = computed(() => {
  const p = Math.min(Math.max(sale.discountPercent || 0, 0), 100);
  return store.maxDiscountPercent > 0 ? Math.min(p, store.maxDiscountPercent) : p;
});
const discountAmount = computed(() => {
  // A flat amount is clamped to net, matching the server's clamp in _apply_order_payload;
  // only the percentage base follows apply_discount_on. The profile cap applies to both
  // (the server measures a flat amount against the line total before tax).
  if (sale.discountMode === 'amount') {
    const amt = Math.min(Math.max(sale.discountAmount || 0, 0), net.value);
    return store.maxDiscountPercent > 0 ? Math.min(amt, (net.value * store.maxDiscountPercent) / 100) : amt;
  }
  return (discountBase.value * effectiveDiscountPercent.value) / 100;
});
const grand = computed(() => Math.max(0, net.value + tax.value - discountAmount.value));

const submitting = ref<'' | 'order' | 'invoice'>('');
const submitError = ref('');
const submittedOrder = ref<SalesOrder | null>(null);
const invoiceOpen = ref(false);

const sheetOpen = ref(false);
const editingLine = ref<CartLine | null>(null);
const editPrice = ref<number>(0);

function openEdit(line: CartLine) {
  if (!store.allowRateChange) return;
  editingLine.value = line;
  editPrice.value = lineRate(line);
  sheetOpen.value = true;
}
function savePrice() {
  if (editingLine.value) sale.setRate(editingLine.value.item.item_code, Number(editPrice.value) || 0);
  sheetOpen.value = false;
}

async function clear() {
  if (await confirm({ title: 'Clear this sale?', message: 'All items will be removed. The customer stays selected.', confirmLabel: 'Clear', tone: 'danger', icon: 'trash' })) {
    sale.reset(true);
    router.replace({ name: 'sell-items' });
  }
}

async function submitOrder(): Promise<SalesOrder> {
  const today = isoToday();
  const itemsPayload = sale.lines.map((line) => ({
    item_code: line.item.item_code,
    item_name: line.item.item_name,
    qty: line.qty,
    rate: lineRate(line),
    amount: line.qty * lineRate(line),
    delivery_date: today,
    stock_uom: line.item.stock_uom,
    price_list_rate: lineRate(line),
  }));
  const discountArgs = store.allowDiscountChange
    ? sale.discountMode === 'percent'
      ? { discountPercent: effectiveDiscountPercent.value }
      // discountAmount (clamped to the subtotal), not the raw input — typing 500
      // against a 100 subtotal must not send 500 to the server.
      : { discountAmount: discountAmount.value || 0 }
    : {};
  let orderName: string;
  if (sale.orderName) {
    await api.updateSalesOrder(sale.orderName, { customer: customer.value!.name, items: itemsPayload, ...discountArgs });
    orderName = sale.orderName;
  } else {
    const res = await api.createSalesOrder({ customer: customer.value!.name, items: itemsPayload, ...discountArgs });
    orderName = res.name;
  }
  return api.submitSalesOrder(orderName);
}

function finish(orderName: string) {
  sale.reset();
  router.replace({ name: 'order', params: { name: orderName } });
}

async function submit(withInvoice: boolean) {
  if (!customer.value || !sale.lines.length || submitting.value) return;
  submitting.value = withInvoice ? 'invoice' : 'order';
  submitError.value = '';
  try {
    const order = await submitOrder();
    if (!withInvoice) {
      toast.success(`Order ${order.name} submitted`);
      finish(order.name);
      return;
    }
    submittedOrder.value = order;
    invoiceOpen.value = true;
  } catch (e: any) {
    submitError.value = e?.message || 'Failed to submit order';
  } finally {
    submitting.value = '';
  }
}

function onInvoiceCreated(invoiceName: string) {
  const name = submittedOrder.value!.name;
  invoiceOpen.value = false;
  toast.success(`Invoice ${invoiceName} created`, { action: { label: 'Print', run: () => api.downloadPdf('Sales Invoice', invoiceName) }, duration: 8000 });
  finish(name);
}
// Sheet dismissed without an invoice: the order is still submitted.
watch(invoiceOpen, (open) => {
  if (!open && submittedOrder.value && sale.hasDraft) {
    const name = submittedOrder.value.name;
    toast.info('Order submitted. You can invoice it from the order.');
    finish(name);
  }
});

onMounted(async () => {
  if (!customer.value) {
    router.replace({ name: 'sell-customer' });
    return;
  }
  if (!sale.lines.length) {
    router.replace({ name: 'sell-items' });
    return;
  }
  if (sale.orderName) {
    orderDetail.value = await api.getSalesOrder(sale.orderName).catch(() => null);
  }
});
</script>
