<template>
  <!--
    Invoicing an order in two steps: how it is paid and which invoice option applies,
    then the server's preview of the very invoice it will save, then confirm.
  -->
  <BottomSheet
    :model-value="modelValue"
    size="lg"
    :title="step === 'setup' ? 'Create invoice' : 'Confirm invoice'"
    :subtitle="order.name"
    :back="step === 'preview'"
    @update:model-value="(v: boolean) => $emit('update:modelValue', v)"
    @back="step = 'setup'"
  >
    <!-- Step 1: payment and option -->
    <div v-if="step === 'setup'" class="space-y-5">
      <div class="space-y-3">
        <p class="text-xs font-bold uppercase tracking-wider text-muted">Payment</p>
        <SegmentedControl
          :model-value="markAsPaid ? 'paid' : 'credit'"
          :options="store.canCreditSale ? [{ value: 'credit', label: 'Credit (pay later)' }, { value: 'paid', label: 'Paid now' }] : [{ value: 'paid', label: 'Paid now' }]"
          @update:model-value="(v: string) => (markAsPaid = v === 'paid')"
        />
        <FormField v-if="markAsPaid" label="Mode of payment" required>
          <BaseSelect v-model="modeOfPayment" placeholder="Select mode">
            <option v-for="mode in paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
          </BaseSelect>
        </FormField>
      </div>

      <div v-if="invoiceOptions.length" class="space-y-3">
        <div>
          <p class="text-xs font-bold uppercase tracking-wider text-muted">Invoice option</p>
          <p class="mt-0.5 text-[12px] text-subtle">Numbering series and tax. Showing options for {{ markAsPaid ? (modeOfPayment ? `payment by ${modeOfPayment}` : 'paid now') : 'credit (pay later)' }}.</p>
        </div>
        <AppAlert v-if="!applicableOptions.length" tone="danger" :message="noOptionMessage" />
        <ChoiceCard
          v-for="opt in applicableOptions"
          :key="opt.name"
          :selected="selectedOption === opt.name"
          :title="opt.option_name"
          :subtitle="`${opt.naming_series} · ${opt.taxes_and_charges || 'No tax'}${opt.description ? ` · ${opt.description}` : ''}`"
          @click="selectedOption = opt.name"
        >
          <template v-if="opt.is_default" #trailing>
            <StatusBadge tone="primary" :dot="false">Default</StatusBadge>
          </template>
        </ChoiceCard>
      </div>

      <AppAlert v-if="error" tone="danger" :message="error" />
    </div>

    <!-- Step 2: preview -->
    <div v-else-if="preview" class="space-y-4">
      <div class="rounded-2xl bg-foreground p-4 text-background">
        <p class="text-[10px] font-bold uppercase tracking-widest opacity-60">Proposed invoice number</p>
        <p class="tnum mt-1 text-2xl font-bold">{{ preview.proposed_name || '—' }}</p>
        <p class="mt-1 text-xs opacity-60">Series {{ preview.naming_series || 'default' }} · the final number is assigned when the invoice is saved.</p>
        <div class="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span v-if="preview.invoice_option" class="rounded-full bg-background/15 px-2.5 py-1 font-semibold">{{ preview.invoice_option.option_name }}</span>
          <span class="rounded-full bg-background/15 px-2.5 py-1">{{ preview.taxes_and_charges || 'No tax' }}</span>
        </div>
      </div>

      <div class="divide-y divide-line rounded-2xl ring-1 ring-inset ring-line">
        <div v-for="line in preview.items" :key="line.item_code" class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
          <div class="min-w-0">
            <p class="truncate font-semibold text-foreground">{{ line.item_name }}</p>
            <p class="tnum text-xs text-muted">{{ qty(line.qty) }} {{ line.uom }} × {{ currency }} {{ money(line.rate) }}</p>
          </div>
          <p class="tnum shrink-0 font-semibold text-foreground">{{ currency }} {{ money(line.amount) }}</p>
        </div>
      </div>

      <div class="space-y-1.5 rounded-2xl bg-card-muted px-4 py-3">
        <DataRow label="Subtotal" :value="`${currency} ${money(preview.total)}`" />
        <DataRow v-if="preview.discount_amount" label="Discount" :value="`− ${currency} ${money(preview.discount_amount)}`" />
        <DataRow v-if="preview.discount_amount || preview.net_total !== preview.total" label="Net total" :value="`${currency} ${money(preview.net_total)}`" />
        <DataRow v-for="(tax, i) in preview.taxes" :key="i" :value="`${currency} ${money(tax.tax_amount)}`">
          <template #label>
            {{ tax.description }}<span v-if="tax.rate"> ({{ tax.rate }}%)</span><span v-if="tax.included_in_print_rate" class="text-subtle"> · inclusive</span>
          </template>
        </DataRow>
        <DataRow v-if="!preview.taxes.length" label="Tax" :value="`${currency} ${money(0)}`" />
        <DataRow label="Grand total" :value="`${currency} ${money(preview.grand_total)}`" emphasis />
        <DataRow v-if="showRounded" label="Rounded total" :value="`${currency} ${money(preview.rounded_total)}`" />
        <div class="flex items-center justify-between pt-1 text-xs text-subtle">
          <span>Payment</span><span>{{ markAsPaid ? `Paid now · ${modeOfPayment}` : 'Credit (collect later)' }}</span>
        </div>
      </div>

      <AppAlert
        v-if="preview.order_taxes_will_update"
        tone="info"
        :message="`The order's taxes will be updated to match this option, so its total changes from ${currency} ${money(preview.order_grand_total)} to ${currency} ${money(preview.grand_total)}.`"
      />
      <AppAlert
        v-if="preview.short_items.length"
        :tone="preview.allow_sale_without_stock ? 'warning' : 'danger'"
        :title="preview.allow_sale_without_stock ? 'Not enough stock' : 'Not enough stock to invoice'"
        :message="preview.allow_sale_without_stock
          ? 'The invoice will be created without updating stock. Whatever is available is delivered now; the rest stays pending until stock arrives.'
          : 'Load the missing stock first, or ask a manager to allow selling without stock on your profile.'"
      />
      <div v-if="preview.short_items.length" class="divide-y divide-line rounded-2xl ring-1 ring-inset ring-line">
        <div v-for="row in preview.short_items" :key="row.item_code" class="flex items-center justify-between gap-3 px-4 py-2.5">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-foreground">{{ row.item_name }}</p>
            <p class="text-xs text-muted">{{ row.item_code }}</p>
          </div>
          <div class="shrink-0 text-right text-xs">
            <p class="tnum font-bold text-danger">{{ qty(row.short_qty) }} {{ row.stock_uom }} short</p>
            <p class="tnum text-muted">Need {{ qty(row.required_qty) }} · Available {{ qty(row.available_qty) }}</p>
          </div>
        </div>
      </div>

      <AppAlert v-if="error" tone="danger" :message="error" />
    </div>

    <template #footer>
      <div v-if="step === 'setup'" class="grid grid-cols-2 gap-2.5">
        <AppButton variant="subtle" size="lg" block @click="$emit('update:modelValue', false)">Cancel</AppButton>
        <AppButton size="lg" block :loading="previewLoading" :disabled="!canContinue" trailing-icon="arrow-right" @click="loadPreview">Continue</AppButton>
      </div>
      <div v-else class="grid grid-cols-2 gap-2.5">
        <AppButton variant="subtle" size="lg" block @click="step = 'setup'">Back</AppButton>
        <AppButton
          size="lg"
          block
          :variant="preview?.short_items.length ? 'warning' : 'primary'"
          icon="check"
          :loading="creating"
          :disabled="creating || !preview || (preview.short_items.length > 0 && !preview.allow_sale_without_stock)"
          @click="create"
        >
          {{ markAsPaid ? 'Create paid invoice' : 'Create invoice' }}
        </AppButton>
      </div>
    </template>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import * as api from '../api/frappe';
import type { SalesOrder, PaymentMode, InvoiceOption, InvoicePreview } from '../types';
import { invoiceOptionApplies } from '../types';
import { useSessionStore } from '../stores/session';
import { money, qty } from '../utils/format';
import { AppAlert, AppButton, BaseSelect, BottomSheet, ChoiceCard, DataRow, FormField, SegmentedControl, StatusBadge } from './ui';

const props = defineProps<{ modelValue: boolean; order: SalesOrder }>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  /** The invoice was saved. `deferredNote` is non-empty when some items await stock. */
  (e: 'created', invoiceName: string, deferredNote: string): void;
}>();

const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);

const step = ref<'setup' | 'preview'>('setup');
// Sales Profile.allow_credit_sale off: every invoice is collected when it is raised.
const markAsPaid = ref(!store.canCreditSale);
const modeOfPayment = ref('');
const paymentModes = ref<PaymentMode[]>([]);
const invoiceOptions = ref<InvoiceOption[]>([]);
const selectedOption = ref<string | null>(null);
const preview = ref<InvoicePreview | null>(null);
const previewLoading = ref(false);
const creating = ref(false);
const error = ref('');
let loaded = false;

// Each option carries a payment rule (credit yes/no, paid-now modes), so the list on
// offer follows the payment choice. The server applies the same rule.
const applicableOptions = computed(() => invoiceOptions.value.filter((opt) => invoiceOptionApplies(opt, markAsPaid.value, modeOfPayment.value)));
const noOptionMessage = computed(() =>
  markAsPaid.value
    ? `None of your invoice options is available for payment by ${modeOfPayment.value || 'this mode'}.`
    : 'None of your invoice options is available for credit invoices.',
);
const canContinue = computed(() => {
  if (markAsPaid.value && !modeOfPayment.value) return false;
  if (invoiceOptions.value.length && !applicableOptions.value.length) return false;
  return true;
});
const showRounded = computed(
  () => !!preview.value && !preview.value.disable_rounded_total && preview.value.rounded_total > 0
    && Math.abs(preview.value.rounded_total - preview.value.grand_total) >= 0.005,
);

// Keep the selection on an applicable option: the default, else the only one.
watch(applicableOptions, (opts) => {
  if (selectedOption.value && opts.some((o) => o.name === selectedOption.value)) return;
  selectedOption.value = opts.find((o) => o.is_default)?.name ?? (opts.length === 1 ? opts[0].name : null);
});

async function loadChoices() {
  if (loaded) return;
  loaded = true;
  const [modes, options] = await Promise.all([
    api.getPaymentModes().catch(() => [] as PaymentMode[]),
    store.capabilities.can_invoice ? api.listInvoiceOptions().catch(() => [] as InvoiceOption[]) : Promise.resolve([] as InvoiceOption[]),
  ]);
  paymentModes.value = modes;
  invoiceOptions.value = options;
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      step.value = 'setup';
      error.value = '';
      preview.value = null;
      loadChoices();
    }
  },
  { immediate: true },
);

async function loadPreview() {
  if (!canContinue.value) return;
  previewLoading.value = true;
  error.value = '';
  try {
    // With one option (or none) the server applies the profile default itself.
    preview.value = await api.previewSalesInvoice(props.order.name, selectedOption.value, {
      markAsPaid: markAsPaid.value,
      modeOfPayment: modeOfPayment.value,
    });
    step.value = 'preview';
  } catch (e: any) {
    error.value = e?.message || 'Failed to prepare the invoice preview';
  } finally {
    previewLoading.value = false;
  }
}

async function create() {
  if (!preview.value) return;
  const withoutStock = preview.value.short_items.length > 0 && preview.value.allow_sale_without_stock;
  creating.value = true;
  error.value = '';
  try {
    const invoiceName = await api.createSalesInvoice(props.order.name, {
      markAsPaid: markAsPaid.value,
      modeOfPayment: modeOfPayment.value,
      allowWithoutStock: withoutStock,
      invoiceOption: selectedOption.value,
    });
    const deferredNote = withoutStock
      ? `Invoice ${invoiceName} created. Available stock was delivered; `
        + `${preview.value.short_items.map((row) => `${qty(row.short_qty)} ${row.stock_uom} ${row.item_name}`).join(', ')} still to be delivered.`
      : '';
    emit('created', invoiceName, deferredNote);
  } catch (e: any) {
    error.value = e?.message || 'Failed to create invoice';
  } finally {
    creating.value = false;
  }
}
</script>
