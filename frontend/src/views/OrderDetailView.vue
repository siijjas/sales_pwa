<template>
  <WorkspacePage back eyebrow="Order detail" :title="order ? order.name : 'Sales Order'" :description="order ? order.customer_name : 'Inspect order lines and actions.'" width="default">
    <template #actions>
      <AppButton variant="secondary" size="sm" icon="refresh" :loading="loading" @click="reload">Refresh</AppButton>
    </template>

    <SkeletonList v-if="loading" :rows="3" height="6rem" />
    <AppAlert v-else-if="error" tone="danger" :message="error" />

    <div v-else-if="order" class="space-y-4 pb-28">
      <AppAlert
        v-if="deferredNotice"
        tone="warning"
        title="Some items are pending delivery"
        :message="deferredNotice"
      />
      <AppAlert v-if="deliveredNotice" tone="success" :message="deliveredNotice" />
      <!-- Summary -->
      <AppCard>
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="text-[11px] font-bold uppercase tracking-wide text-muted">Customer</p>
            <p class="truncate text-lg font-bold text-foreground">{{ order.customer_name }}</p>
            <p class="text-xs text-muted">{{ order.customer }} • {{ order.transaction_date }}</p>
          </div>
          <div class="flex flex-col items-end gap-2">
            <StatusBadge :status="order.status" />
            <StatusBadge :tone="docTone(order.docstatus)" :dot="false">{{ docLabel(order.docstatus) }}</StatusBadge>
          </div>
        </div>
        <div class="mt-4 space-y-2 border-t border-line pt-4">
          <div class="flex items-center justify-between text-base font-bold text-foreground">
            <span>Grand total</span><span class="tnum">{{ currency }} {{ fmt(order.grand_total) }}</span>
          </div>
          <div class="flex items-center justify-between text-xs text-muted">
            <span>Company</span><span>{{ order.company || '—' }}</span>
          </div>
          <div class="flex items-center justify-between text-xs text-muted">
            <span>Price list</span><span>{{ order.selling_price_list || '—' }}</span>
          </div>
        </div>
      </AppCard>

      <!-- Items -->
      <AppCard padding="none">
        <div class="border-b border-line px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted">
          Items ({{ order.items.length }})
        </div>
        <div class="divide-y divide-line">
          <div v-for="line in order.items" :key="line.item_code" class="flex items-start justify-between gap-3 p-4">
            <div class="min-w-0">
              <p class="font-semibold text-foreground">{{ line.item_name }}</p>
              <p class="text-xs text-muted">{{ line.item_code }}<span v-if="line.stock_uom"> • {{ line.stock_uom }}</span></p>
              <p v-if="line.delivery_date" class="mt-1 text-[11px] text-subtle">Delivery {{ line.delivery_date }}</p>
            </div>
            <div class="shrink-0 text-right">
              <p class="tnum text-sm font-bold text-foreground">{{ currency }} {{ fmt(line.amount) }}</p>
              <p class="tnum text-xs text-muted">{{ line.qty }} × {{ currency }} {{ line.rate?.toFixed(2) }}</p>
            </div>
          </div>
        </div>
      </AppCard>

      <!-- Secondary actions -->
      <div class="flex flex-wrap gap-2">
        <AppButton v-if="order.docstatus === 0" variant="secondary" size="sm" icon="edit" @click="editItems">Edit items</AppButton>
        <AppButton v-if="order.docstatus === 0" variant="secondary" size="sm" icon="plus" @click="addMoreItems">Add items</AppButton>
        <AppButton v-if="order.docstatus === 1" variant="secondary" size="sm" icon="printer" @click="printPdf">Print receipt</AppButton>
      </div>

      <!-- Invoicing options (Van Sales only; Field Sales orders are billed by the back office) -->
      <AppAlert
        v-if="!canInvoice && order.docstatus === 1 && (order.per_billed ?? 0) < 100"
        tone="info"
        message="This order is submitted. Invoicing and delivery are handled by the back office."
      />
      <AppCard v-if="canInvoice && order.docstatus === 1 && (order.per_billed ?? 0) < 100">
        <div class="space-y-3">
          <label class="text-xs font-bold uppercase tracking-wider text-muted">Invoice type</label>
          <SegmentedControl
            :model-value="markAsPaid ? 'paid' : 'credit'"
            :options="canCreditSale ? [{ value: 'credit', label: 'Credit (pay later)' }, { value: 'paid', label: 'Paid now' }] : [{ value: 'paid', label: 'Paid now' }]"
            @update:modelValue="(v: string) => (markAsPaid = v === 'paid')"
          />
          <FormField v-if="markAsPaid" label="Mode of payment" required>
            <BaseSelect v-model="modeOfPayment" placeholder="Select mode">
              <option v-for="mode in paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
            </BaseSelect>
          </FormField>
        </div>
      </AppCard>
    </div>

    <!-- Primary action -->
    <StickyBar v-if="order && order.docstatus === 0">
      <AppButton size="lg" block icon="check" :loading="submitting" @click="submitOrder">
        {{ submitting ? 'Submitting…' : 'Submit order' }}
      </AppButton>
    </StickyBar>
    <StickyBar v-else-if="canInvoice && order && order.docstatus === 1 && (order.per_billed ?? 0) < 100">
      <AppAlert v-if="invoiceCreated" tone="success" :message="`Invoice ${invoiceCreated} created`" class="mb-2" />
      <AppButton
        size="lg"
        block
        icon="file-text"
        :loading="invoicing"
        :disabled="markAsPaid && !modeOfPayment"
        @click="createInvoice"
      >
        {{ invoicing ? 'Creating invoice…' : previewLoading ? 'Preparing preview…' : markAsPaid ? 'Create paid invoice' : 'Create sales invoice' }}
      </AppButton>
    </StickyBar>
    <StickyBar v-else-if="canDeliver && hasPendingDelivery">
      <AppButton size="lg" block icon="truck" :loading="delivering" @click="deliverPending">
        {{ delivering ? 'Delivering…' : 'Deliver pending items' }}
      </AppButton>
    </StickyBar>

    <!-- Step 1: which invoice option (numbering series + tax template) -->
    <BottomSheet v-model="optionSheetOpen" title="Invoice option">
      <div class="space-y-3">
        <p class="text-sm text-muted">Choose how this invoice is numbered and taxed. You will see the proposed number and totals before anything is created.</p>
        <AppAlert v-if="sheetError" tone="danger" :message="sheetError" />
        <button
          v-for="opt in invoiceOptions"
          :key="opt.name"
          type="button"
          class="flex w-full items-center gap-3 rounded-2xl border p-3.5 text-left transition hover:bg-card-muted"
          :class="opt.is_default ? 'border-primary/40 bg-primary/[0.05]' : 'border-line'"
          :disabled="previewLoading"
          @click="openPreview(opt.name)"
        >
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary"><AppIcon name="file-text" :size="18" /></span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2">
              <span class="truncate font-semibold text-foreground">{{ opt.option_name }}</span>
              <StatusBadge v-if="opt.is_default" tone="primary" :dot="false">Default</StatusBadge>
            </span>
            <span class="block truncate text-xs text-muted">{{ opt.naming_series }} · {{ opt.taxes_and_charges || 'No tax' }}</span>
            <span v-if="opt.description" class="block truncate text-xs text-subtle">{{ opt.description }}</span>
          </span>
          <AppIcon name="chevron-right" :size="16" class="shrink-0 text-subtle" />
        </button>
      </div>
    </BottomSheet>

    <!-- Step 2: preview, then confirm -->
    <BottomSheet v-model="previewOpen" title="Confirm invoice">
      <div v-if="preview" class="space-y-4">
        <AppAlert v-if="sheetError" tone="danger" :message="sheetError" />

        <div class="rounded-2xl bg-slate-950 p-4 text-white">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Proposed invoice number</p>
          <p class="tnum mt-1 text-2xl font-bold">{{ preview.proposed_name || '—' }}</p>
          <p class="mt-1 text-xs text-slate-400">
            Series {{ preview.naming_series || 'default' }} · the final number is assigned when the invoice is saved.
          </p>
          <div v-if="preview.invoice_option" class="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span class="rounded-full bg-white/10 px-2.5 py-1 font-semibold">{{ preview.invoice_option.option_name }}</span>
            <span class="rounded-full bg-white/10 px-2.5 py-1">{{ preview.taxes_and_charges || 'No tax' }}</span>
          </div>
        </div>

        <div class="divide-y divide-line rounded-2xl border border-line">
          <div v-for="line in preview.items" :key="line.item_code" class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
            <div class="min-w-0">
              <p class="truncate font-semibold text-foreground">{{ line.item_name }}</p>
              <p class="tnum text-xs text-muted">{{ line.qty }} {{ line.uom }} × {{ currency }} {{ fmt(line.rate) }}</p>
            </div>
            <p class="tnum shrink-0 font-semibold text-foreground">{{ currency }} {{ fmt(line.amount) }}</p>
          </div>
        </div>

        <div class="space-y-1.5 rounded-2xl bg-card-muted px-4 py-3 text-sm">
          <div class="flex items-center justify-between text-muted"><span>Subtotal</span><span class="tnum">{{ currency }} {{ fmt(preview.total) }}</span></div>
          <div v-if="preview.discount_amount" class="flex items-center justify-between text-muted"><span>Discount</span><span class="tnum">− {{ currency }} {{ fmt(preview.discount_amount) }}</span></div>
          <div v-if="preview.discount_amount || preview.net_total !== preview.total" class="flex items-center justify-between text-muted"><span>Net total</span><span class="tnum">{{ currency }} {{ fmt(preview.net_total) }}</span></div>
          <div v-for="(tax, i) in preview.taxes" :key="i" class="flex items-center justify-between text-muted">
            <span>{{ tax.description }}<span v-if="tax.rate"> ({{ tax.rate }}%)</span><span v-if="tax.included_in_print_rate" class="text-subtle"> · inclusive</span></span>
            <span class="tnum">{{ currency }} {{ fmt(tax.tax_amount) }}</span>
          </div>
          <div v-if="!preview.taxes.length" class="flex items-center justify-between text-muted"><span>Tax</span><span class="tnum">{{ currency }} {{ fmt(0) }}</span></div>
          <div class="flex items-center justify-between border-t border-line pt-2 text-base font-bold text-foreground">
            <span>Grand total</span><span class="tnum">{{ currency }} {{ fmt(preview.grand_total) }}</span>
          </div>
          <div v-if="showRounded" class="flex items-center justify-between text-muted">
            <span>Rounded total</span><span class="tnum">{{ currency }} {{ fmt(preview.rounded_total) }}</span>
          </div>
          <div class="flex items-center justify-between pt-1 text-xs text-subtle">
            <span>Payment</span><span>{{ markAsPaid ? `Paid now · ${modeOfPayment}` : 'Credit (collect later)' }}</span>
          </div>
        </div>

        <AppAlert
          v-if="preview.short_items.length"
          :tone="preview.allow_sale_without_stock ? 'warning' : 'danger'"
          :title="preview.allow_sale_without_stock ? 'Not enough stock' : 'Not enough stock to invoice'"
          :message="preview.allow_sale_without_stock
            ? 'The invoice will be created without updating stock. Whatever is available is delivered now; the rest stays pending until stock arrives.'
            : 'Load the missing stock first, or ask a manager to allow selling without stock on your profile.'"
        />
        <div v-if="preview.short_items.length" class="divide-y divide-line rounded-2xl border border-line">
          <div v-for="row in preview.short_items" :key="row.item_code" class="flex items-center justify-between gap-3 px-4 py-2.5">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-foreground">{{ row.item_name }}</p>
              <p class="text-xs text-muted">{{ row.item_code }}</p>
            </div>
            <div class="shrink-0 text-right text-xs">
              <p class="tnum font-bold text-danger">{{ row.short_qty }} {{ row.stock_uom }} short</p>
              <p class="tnum text-muted">Need {{ row.required_qty }} • Available {{ row.available_qty }}</p>
            </div>
          </div>
        </div>

        <div class="flex gap-2">
          <AppButton variant="secondary" block @click="backFromPreview">{{ invoiceOptions.length > 1 ? 'Change option' : 'Cancel' }}</AppButton>
          <AppButton
            :variant="preview.short_items.length ? 'warning' : 'primary'"
            block
            icon="check"
            :loading="invoicing"
            :disabled="invoicing || (preview.short_items.length > 0 && !preview.allow_sale_without_stock)"
            @click="confirmInvoice"
          >
            {{ markAsPaid ? 'Create paid invoice' : 'Create invoice' }}
          </AppButton>
        </div>
      </div>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { SalesOrder, PaymentMode, InvoiceOption, InvoicePreview } from '../types';
import { useSessionStore } from '../stores/session';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, StatusBadge, SkeletonList, StickyBar, SegmentedControl, FormField, BaseSelect, BottomSheet } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const canInvoice = computed(() => store.capabilities.can_invoice);
const canDeliver = computed(() => store.capabilities.can_deliver);
const orderId = route.params.name as string;

const order = ref<SalesOrder | null>(null);
const loading = ref(true);
const error = ref('');
const submitting = ref(false);
const invoicing = ref(false);
const invoiceCreated = ref('');
// Sales Profile.allow_credit_sale off: every invoice is collected when it is raised.
const canCreditSale = computed(() => store.isManager || store.capabilities.can_credit_sale !== false);
const markAsPaid = ref(!canCreditSale.value);
const modeOfPayment = ref('');
const paymentModes = ref<PaymentMode[]>([]);
// Invoicing runs as: pick an invoice option (numbering series + tax template, when the
// profile lists more than one) → preview the proposed number and totals → confirm.
// The preview comes from the server building the very invoice it will then save.
const invoiceOptions = ref<InvoiceOption[]>([]);
const optionSheetOpen = ref(false);
const previewOpen = ref(false);
const previewLoading = ref(false);
const preview = ref<InvoicePreview | null>(null);
const selectedOption = ref<string | null>(null);
const sheetError = ref('');
const deferredNotice = ref('');
const showRounded = computed(
  () => !!preview.value && !preview.value.disable_rounded_total && preview.value.rounded_total > 0
    && Math.abs(preview.value.rounded_total - preview.value.grand_total) >= 0.005,
);
const delivering = ref(false);
const deliveredNotice = ref('');
// Billed in full but not yet delivered in full: sold while short of van stock.
const hasPendingDelivery = computed(
  () => !!order.value && order.value.docstatus === 1 && (order.value.per_billed ?? 0) >= 100
    && (order.value.per_delivered ?? 100) < 100 && order.value.status !== 'Closed',
);

const fmt = (n?: number) => (n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    order.value = await api.getSalesOrder(orderId);
  } catch (e: any) {
    error.value = e?.message || 'Failed to load order';
  } finally {
    loading.value = false;
  }
};
onMounted(() => {
  load();
  api.getPaymentModes().then((modes) => (paymentModes.value = modes)).catch(() => {});
  if (canInvoice.value) {
    api.listInvoiceOptions().then((opts) => (invoiceOptions.value = opts)).catch(() => {});
  }
});
const reload = () => load();

const submitOrder = async () => {
  if (!order.value || order.value.docstatus !== 0) return;
  submitting.value = true;
  error.value = '';
  try {
    order.value = await api.getSalesOrder(order.value.name);
    await api.submitSalesOrder(order.value.name);
    await load();
  } catch (e: any) {
    error.value = e?.message || 'Failed to submit order';
  } finally {
    submitting.value = false;
  }
};

const createInvoice = async () => {
  if (!order.value || order.value.docstatus !== 1) return;
  if (markAsPaid.value && !modeOfPayment.value) {
    error.value = 'Select a mode of payment to mark this invoice as paid.';
    return;
  }
  error.value = '';
  sheetError.value = '';
  if (invoiceOptions.value.length > 1) {
    optionSheetOpen.value = true;
    return;
  }
  // One option (or none): the server applies the profile default, straight to the preview.
  await openPreview(invoiceOptions.value[0]?.name ?? null);
};

const openPreview = async (option: string | null) => {
  if (!order.value) return;
  previewLoading.value = true;
  sheetError.value = '';
  try {
    preview.value = await api.previewSalesInvoice(order.value.name, option);
    selectedOption.value = option;
    optionSheetOpen.value = false;
    previewOpen.value = true;
  } catch (e: any) {
    const message = e?.message || 'Failed to prepare the invoice preview';
    if (optionSheetOpen.value) sheetError.value = message;
    else error.value = message;
  } finally {
    previewLoading.value = false;
  }
};

const backFromPreview = () => {
  previewOpen.value = false;
  if (invoiceOptions.value.length > 1) optionSheetOpen.value = true;
};

const confirmInvoice = async () => {
  if (!order.value || !preview.value) return;
  const withoutStock = preview.value.short_items.length > 0 && preview.value.allow_sale_without_stock;
  invoicing.value = true;
  sheetError.value = '';
  try {
    invoiceCreated.value = await api.createSalesInvoice(order.value.name, {
      markAsPaid: markAsPaid.value,
      modeOfPayment: modeOfPayment.value,
      allowWithoutStock: withoutStock,
      invoiceOption: selectedOption.value,
    });
    deferredNotice.value = withoutStock
      ? `Invoice ${invoiceCreated.value} created. Available stock was delivered; `
        + `${preview.value.short_items.map((row) => `${row.short_qty} ${row.stock_uom} ${row.item_name}`).join(', ')} still to be delivered.`
      : '';
    previewOpen.value = false;
    preview.value = null;
    await load();
  } catch (e: any) {
    sheetError.value = e?.message || 'Failed to create invoice';
  } finally {
    invoicing.value = false;
  }
};

const deliverPending = async () => {
  if (!order.value) return;
  delivering.value = true;
  error.value = '';
  try {
    const notes = await api.deliverPendingItems(order.value.name);
    deliveredNotice.value = `Delivered from van: ${notes.join(', ')}`;
    deferredNotice.value = '';
    await load();
  } catch (e: any) {
    error.value = e?.message || 'Failed to deliver pending items';
  } finally {
    delivering.value = false;
  }
};

const printPdf = () => api.downloadPdf('Sales Order', orderId);

const seedCart = () => {
  if (!order.value) return;
  store.setCustomer({ name: order.value.customer, customer_name: order.value.customer_name, customer_group: '', territory: '' });
  store.setCurrentOrder(order.value.name);
  store.setCartFromOrder(order.value.items || []);
};
const editItems = () => {
  seedCart();
  router.push({ name: 'cart' });
};
const addMoreItems = () => {
  seedCart();
  router.push({ name: 'items', query: { customer: order.value!.customer, customer_name: order.value!.customer_name } });
};

const docLabel = (d: number) => (d === 0 ? 'Draft' : d === 1 ? 'Submitted' : d === 2 ? 'Cancelled' : 'Unknown');
const docTone = (d: number): 'success' | 'danger' | 'warning' => (d === 1 ? 'success' : d === 2 ? 'danger' : 'warning');
</script>
