<template>
  <div class="flex min-h-dvh flex-col px-3 pb-4 pt-safe md:px-5 xl:h-dvh xl:min-h-0">
    <!-- Header -->
    <div class="flex flex-wrap items-end justify-between gap-3 pb-3 pt-4 md:pt-5">
      <div class="min-w-0">
        <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-primary">Counter</p>
        <h1 class="truncate text-[22px] font-bold leading-tight tracking-tight text-foreground md:text-[26px]">
          {{ counter.orderName ? `Editing ${counter.orderName}` : 'New sale' }}
        </h1>
        <p class="mt-0.5 truncate text-[12.5px] text-muted">
          {{ store.workspaceLabel }}<template v-if="warehouse"> · {{ warehouse }}</template><template v-if="priceList"> · {{ priceList }}</template>
        </p>
      </div>
      <div class="hidden flex-wrap items-center gap-1.5 text-[11px] text-muted lg:flex">
        <span v-for="k in KEYS" :key="k.key" class="inline-flex items-center gap-1 rounded-lg bg-card-muted px-2 py-1">
          <kbd class="tnum rounded-md bg-card px-1.5 py-0.5 font-bold text-foreground shadow-card">{{ k.key }}</kbd>{{ k.label }}
        </span>
      </div>
    </div>

    <AppAlert
      v-if="shift.needsShift"
      tone="warning"
      icon="clock"
      :title="shift.isStale ? 'Close yesterday’s shift first' : 'Open your shift first'"
      message="Selling is blocked until today’s shift is open."
      class="mb-3"
    >
      <AppButton size="sm" class="mt-2" @click="router.push(shift.gateRoute)">{{ shift.isStale ? 'Close shift' : 'Open shift' }}</AppButton>
    </AppAlert>
    <AppAlert v-if="screenNote" tone="info" :message="screenNote" class="mb-3 lg:hidden" />

    <div class="grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1fr)_23rem]">
      <!-- ─── Left: customer and lines ───────────────────────────────── -->
      <div class="flex min-h-0 flex-col gap-3">
        <AppCard padding="sm">
          <div class="flex flex-wrap items-center gap-3">
            <CustomerBox ref="customerBox" class="min-w-[16rem] flex-1" :model-value="counter.customer" :can-create="store.canCreateCustomer" @update:model-value="onCustomer" @picked="focusEntry" />
            <div v-if="counter.customer && store.showsCustomerBalance" class="flex items-center gap-2 text-[12.5px]">
              <span class="text-muted">Outstanding</span>
              <span class="tnum font-bold" :class="(summary?.outstanding_balance || 0) > 0 ? 'text-warning' : 'text-foreground'">
                {{ currency }} {{ money(summary?.outstanding_balance || 0) }}
              </span>
              <RouterLink v-if="counter.customer" :to="{ name: 'customer', params: { name: counter.customer.name } }" tabindex="-1" class="font-semibold text-primary hover:underline">Open</RouterLink>
            </div>
          </div>
        </AppCard>

        <AppCard padding="none" class="flex min-h-[20rem] flex-1 flex-col xl:min-h-0">
          <div class="min-h-0 flex-1 overflow-y-auto">
            <table class="w-full table-fixed text-[14px]">
              <thead class="sticky top-0 z-10 bg-card text-[11.5px] font-bold uppercase tracking-wide text-muted shadow-[0_1px_0_rgb(var(--c-line))]">
                <tr>
                  <th class="w-9 px-3 py-2 text-left">#</th>
                  <th class="px-2 py-2 text-left">Item</th>
                  <th class="w-24 px-2 py-2 text-right">Qty</th>
                  <th class="w-16 px-2 py-2 text-left">UOM</th>
                  <th class="w-28 px-2 py-2 text-right">Rate</th>
                  <th class="w-32 px-2 py-2 text-right">Amount</th>
                  <th class="w-24 px-2 py-2 text-right">Stock</th>
                  <th class="w-10 px-2 py-2"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-if="!counter.lines.length">
                  <td colspan="8" class="px-4 py-10 text-center text-[13.5px] text-muted">
                    No lines yet. Type an item code or name below, enter the quantity and press Enter.
                  </td>
                </tr>
                <tr v-for="(line, idx) in counter.lines" :key="line.uid" class="group" :class="shortByItem[line.item.item_code] ? 'bg-warning/[0.06]' : ''">
                  <td class="tnum px-3 py-1.5 text-muted">{{ idx + 1 }}</td>
                  <td class="px-2 py-1.5">
                    <p class="truncate font-semibold text-foreground">{{ line.item.item_name }}</p>
                    <p class="truncate text-[12px] text-muted">{{ line.item.item_code }}</p>
                  </td>
                  <td class="px-2 py-1.5">
                    <input
                      :ref="(el) => setQtyRef(line.uid, el as HTMLInputElement | null)"
                      :value="qtyFmt(line.qty)"
                      type="text"
                      inputmode="decimal"
                      class="field-inline w-full"
                      @focus="($event.target as HTMLInputElement).select()"
                      @change="counter.setQty(line.uid, parseNum(($event.target as HTMLInputElement).value))"
                      @keydown="onLineKeydown($event, line.uid, idx)"
                    />
                  </td>
                  <td class="px-2 py-1.5 text-[12.5px] text-muted">{{ line.item.stock_uom }}</td>
                  <td class="px-2 py-1.5 text-right">
                    <input
                      v-if="allowRate"
                      :value="money(line.rate)"
                      type="text"
                      inputmode="decimal"
                      class="field-inline w-full"
                      @focus="($event.target as HTMLInputElement).select()"
                      @change="counter.setRate(line.uid, parseNum(($event.target as HTMLInputElement).value))"
                      @keydown.enter.prevent="focusEntry"
                    />
                    <span v-else class="tnum font-semibold text-foreground">{{ money(line.rate) }}</span>
                  </td>
                  <td class="tnum px-2 py-1.5 text-right font-bold text-foreground">{{ money(line.qty * line.rate) }}</td>
                  <td class="px-2 py-1.5 text-right">
                    <StatusBadge v-if="shortByItem[line.item.item_code]" tone="warning" :dot="false">Short {{ qtyFmt(shortByItem[line.item.item_code].short_qty) }}</StatusBadge>
                    <StatusBadge v-else-if="line.item.actual_qty !== null && line.item.is_stock_item" :tone="line.item.actual_qty <= 0 ? 'danger' : line.item.actual_qty < 5 ? 'warning' : 'success'" :dot="false">{{ qtyFmt(line.item.actual_qty) }}</StatusBadge>
                  </td>
                  <td class="px-2 py-1.5 text-right">
                    <button type="button" tabindex="-1" class="flex h-8 w-8 items-center justify-center rounded-full text-subtle opacity-0 transition hover:bg-danger/10 hover:text-danger focus:opacity-100 group-hover:opacity-100" aria-label="Remove line" @click="counter.removeLine(line.uid)">
                      <AppIcon name="trash" :size="15" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="border-t border-line bg-elevated p-2.5">
            <ItemEntryRow
              ref="entryRow"
              :customer="counter.customer?.name || null"
              :currency="currency"
              :allow-rate="allowRate"
              :allow-without-stock="allowWithoutStock"
              @add="onAdd"
              @up="focusLastLine"
            />
          </div>
        </AppCard>
      </div>

      <!-- ─── Right: totals, payment, actions, queue ──────────────────── -->
      <div class="flex min-h-0 flex-col gap-3 xl:overflow-y-auto">
        <AppCard padding="sm" class="space-y-1.5">
          <AppAlert v-if="preview?.error" tone="danger" :message="preview.error" class="mb-2" />
          <DataRow label="Items" :value="`${counter.lines.length} · qty ${qtyFmt(counter.count)}`" />
          <DataRow label="Subtotal" :value="`${currency} ${money(preview && !preview.error ? preview.total : counter.subtotal)}`" />
          <div v-if="allowDiscount" class="flex items-center justify-between gap-2 py-1">
            <span class="text-[13px] text-muted">Discount</span>
            <div class="flex items-center gap-1.5">
              <button type="button" tabindex="-1" class="rounded-lg bg-card-muted px-2 py-1 text-[12px] font-bold text-foreground" @click="counter.setDiscount(counter.discountMode === 'percent' ? 'amount' : 'percent', 0)">
                {{ counter.discountMode === 'percent' ? '%' : currency }}
              </button>
              <input
                ref="discountInput"
                :value="counter.discountMode === 'percent' ? counter.discountPercent || '' : counter.discountAmount || ''"
                type="text"
                inputmode="decimal"
                placeholder="0"
                class="field-inline w-20"
                @focus="($event.target as HTMLInputElement).select()"
                @change="onDiscount(($event.target as HTMLInputElement).value)"
                @keydown.enter.prevent="focusEntry"
              />
            </div>
          </div>
          <DataRow v-if="preview && !preview.error && preview.discount_amount" label="Discount applied" :value="`− ${currency} ${money(preview.discount_amount)}`" />
          <DataRow v-for="tax in preview && !preview.error ? preview.taxes : []" :key="tax.description" :label="tax.included_in_print_rate ? `${tax.description} (incl.)` : tax.description" :value="`${currency} ${money(tax.tax_amount)}`" />
          <div class="flex items-end justify-between border-t border-line pt-2">
            <div>
              <p class="text-[12px] font-bold uppercase tracking-wide text-muted">Total</p>
              <p v-if="preview?.proposed_invoice_name && counter.lines.length" class="text-[11.5px] text-subtle">Next invoice {{ preview.proposed_invoice_name }}</p>
            </div>
            <p class="tnum text-[28px] font-bold leading-none tracking-tight text-foreground" :class="previewLoading ? 'opacity-60' : ''">
              {{ currency }} {{ money(grandTotal) }}
            </p>
          </div>
          <p v-if="showRounded" class="text-right text-[11.5px] text-muted">Before rounding {{ currency }} {{ money(preview!.grand_total) }}</p>
        </AppCard>

        <AppCard padding="sm" class="space-y-2.5">
          <SegmentedControl
            v-if="store.canCreditSale"
            :model-value="counter.markAsPaid ? 'paid' : 'credit'"
            :options="[{ value: 'paid', label: 'Paid now' }, { value: 'credit', label: 'Credit' }]"
            @update:model-value="(v: string) => setPayment(v === 'paid', counter.modeOfPayment, counter.invoiceOption)"
          />
          <div class="grid gap-2" :class="invoiceOptions.length ? 'grid-cols-2' : ''">
            <FormField v-if="counter.markAsPaid" label="Mode of payment">
              <BaseSelect :model-value="counter.modeOfPayment" placeholder="Select mode" @update:model-value="(v) => setPayment(true, v, counter.invoiceOption)">
                <option v-for="m in paymentModes" :key="m.name" :value="m.name">{{ m.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="invoiceOptions.length" label="Invoice option">
              <BaseSelect :model-value="counter.invoiceOption || ''" :placeholder="applicableOptions.length ? 'Select option' : 'None fits this payment'" @update:model-value="(v) => setPayment(counter.markAsPaid, counter.modeOfPayment, v || null)">
                <option v-for="o in applicableOptions" :key="o.name" :value="o.name">{{ o.option_name }}</option>
              </BaseSelect>
            </FormField>
          </div>
          <ToggleSwitch v-if="printsDirectly('Sales Invoice')" :model-value="counter.autoPrint" label="Print the invoice as soon as it is raised" @update:model-value="counter.setAutoPrint" />
        </AppCard>

        <div class="grid grid-cols-2 gap-2">
          <AppButton size="lg" block icon="file-text" class="col-span-2" :loading="busy === 'invoice'" :disabled="!canSubmit || !!busy" @click="submit(true)">Submit &amp; invoice <kbd class="ml-1 text-[11px] opacity-70">F9</kbd></AppButton>
          <AppButton size="md" block variant="secondary" :loading="busy === 'order'" :disabled="!canSubmit || !!busy" @click="submit(false)">Submit order <kbd class="ml-1 text-[11px] opacity-70">F8</kbd></AppButton>
          <AppButton size="md" block variant="subtle" icon="save" :loading="busy === 'hold'" :disabled="!canSubmit || !!busy" @click="hold">Hold <kbd class="ml-1 text-[11px] opacity-70">F7</kbd></AppButton>
          <AppButton size="sm" block variant="subtle" icon="printer" :disabled="!lastInvoice" @click="printLast">Print last <kbd class="ml-1 text-[11px] opacity-70">F10</kbd></AppButton>
          <AppButton size="sm" block variant="ghost" icon="trash" :disabled="!counter.hasLines && !counter.customer" @click="clear">Clear <kbd class="ml-1 text-[11px] opacity-70">Esc</kbd></AppButton>
        </div>

        <CounterQueue ref="queuePanel" class="min-h-[14rem] flex-1" :queue="queue" :loading="queueLoading" :busy="!!busy" :currency="currency" @refresh="loadQueue" @resume="resume" @invoice="openInvoiceSheet" @print="(row) => print('Sales Invoice', row.name)" />
      </div>
    </div>

    <InvoiceSheet v-if="sheetOrder" v-model="sheetOpen" :order="sheetOrder" @created="onSheetInvoiced" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { CounterItem, CounterPreview, CounterQueue as CounterQueueData, CounterQueueOrder, Customer, CustomerSummary, InvoiceOption, InvoiceStockShortage, PaymentMode, SalesOrder } from '../types';
import { invoiceOptionApplies } from '../types';
import { useSessionStore } from '../stores/session';
import { useCounterStore } from '../stores/counter';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { usePrint } from '../composables/usePrint';
import { useConfirm } from '../composables/useConfirm';
import { money, qty as qtyFmt, isoToday } from '../utils/format';
import InvoiceSheet from '../components/InvoiceSheet.vue';
import CustomerBox from '../components/counter/CustomerBox.vue';
import ItemEntryRow from '../components/counter/ItemEntryRow.vue';
import CounterQueue from '../components/counter/CounterQueue.vue';
import { AppAlert, AppButton, AppCard, AppIcon, BaseSelect, DataRow, FormField, SegmentedControl, StatusBadge, ToggleSwitch } from '../components/ui';

const KEYS = [
  { key: 'F2', label: 'Customer' },
  { key: 'F3', label: 'Item' },
  { key: 'F4', label: 'Discount' },
  { key: 'F7', label: 'Hold' },
  { key: 'F8', label: 'Submit' },
  { key: 'F9', label: 'Invoice' },
  { key: 'F10', label: 'Print' },
  { key: 'Esc', label: 'Clear' },
];

const store = useSessionStore();
const counter = useCounterStore();
const shift = useShiftStore();
const router = useRouter();
const toast = useToast();
const { print, printsDirectly } = usePrint();
const { confirm } = useConfirm();

const customerBox = ref<InstanceType<typeof CustomerBox> | null>(null);
const entryRow = ref<InstanceType<typeof ItemEntryRow> | null>(null);
const queuePanel = ref<InstanceType<typeof CounterQueue> | null>(null);
const discountInput = ref<HTMLInputElement | null>(null);
const qtyRefs = new Map<string, HTMLInputElement>();
const setQtyRef = (uid: string, el: HTMLInputElement | null) => (el ? qtyRefs.set(uid, el) : qtyRefs.delete(uid));

const currency = computed(() => store.currencyDisplay);
const allowRate = computed(() => store.allowRateChange);
const allowDiscount = computed(() => store.allowDiscountChange);
const allowWithoutStock = computed(() => Boolean(store.driverConfig?.allow_sale_without_stock));
const warehouse = computed(() => preview.value?.warehouse || store.driverConfig?.selling_warehouse || '');
const priceList = ref<string | null>(store.driverConfig?.selling_price_list || null);
const screenNote = computed(() => (window.innerWidth < 1024 ? 'The Counter is laid out for a PC keyboard; on a phone use Sell instead.' : ''));

const defaultCustomer = computed<Customer | null>(() => {
  const cfg = store.driverConfig;
  if (!cfg?.default_customer) return null;
  return { name: cfg.default_customer, customer_name: cfg.default_customer_name || cfg.default_customer, customer_group: '', territory: '' };
});

// ─── Preview: ERPNext's totals for the cart as it stands ────────────────
const preview = ref<CounterPreview | null>(null);
const previewLoading = ref(false);
let previewTimer: number | undefined;
let previewSeq = 0;

const cartPayload = (): api.CounterCartPayload => ({
  customer: counter.customer!.name,
  items: counter.lines.map((l) => ({ item_code: l.item.item_code, qty: l.qty, ...(allowRate.value ? { rate: l.rate } : {}) })),
  discountPercent: allowDiscount.value && counter.discountMode === 'percent' ? counter.discountPercent || 0 : 0,
  discountAmount: allowDiscount.value && counter.discountMode === 'amount' ? counter.discountAmount || 0 : 0,
});
const paymentPayload = () => ({
  markAsPaid: counter.markAsPaid,
  modeOfPayment: counter.markAsPaid ? counter.modeOfPayment : null,
  invoiceOption: counter.invoiceOption,
});

function schedulePreview() {
  window.clearTimeout(previewTimer);
  if (!counter.customer || !counter.lines.length) {
    preview.value = null;
    previewLoading.value = false;
    return;
  }
  previewLoading.value = true;
  const seq = ++previewSeq;
  previewTimer = window.setTimeout(async () => {
    try {
      const res = await api.previewCounterTotals(cartPayload(), paymentPayload());
      if (seq !== previewSeq) return;
      preview.value = res;
      // Staff who cannot change rates see the rate ERPNext priced (pricing rules included).
      if (!allowRate.value && !res.error && res.lines.length === counter.lines.length) {
        res.lines.forEach((row, i) => {
          const line = counter.lines[i];
          if (line.item.item_code === row.item_code && Math.abs(line.rate - row.rate) > 0.004) counter.setRate(line.uid, row.rate);
        });
      }
    } catch (e: any) {
      if (seq === previewSeq) preview.value = { ...(preview.value as CounterPreview), error: e?.message || 'Could not compute totals' } as CounterPreview;
    } finally {
      if (seq === previewSeq) previewLoading.value = false;
    }
  }, 250);
}

watch(
  () => [counter.customer?.name, counter.lines.map((l) => `${l.item.item_code}:${l.qty}:${l.rate}`).join('|'), counter.discountMode, counter.discountPercent, counter.discountAmount, counter.markAsPaid, counter.modeOfPayment, counter.invoiceOption],
  schedulePreview,
);

const grandTotal = computed(() => {
  const p = preview.value;
  if (!p || p.error) return counter.subtotal;
  return !p.disable_rounded_total && p.rounded_total > 0 ? p.rounded_total : p.grand_total;
});
const showRounded = computed(() => {
  const p = preview.value;
  return !!p && !p.error && !p.disable_rounded_total && p.rounded_total > 0 && Math.abs(p.rounded_total - p.grand_total) >= 0.005;
});
const shortByItem = computed<Record<string, InvoiceStockShortage>>(() => {
  const map: Record<string, InvoiceStockShortage> = {};
  for (const row of preview.value?.short_items || []) map[row.item_code] = row;
  return map;
});

// ─── Customer ───────────────────────────────────────────────────────────
const summary = ref<CustomerSummary | null>(null);
function onCustomer(c: Customer | null) {
  counter.setCustomer(c);
}
watch(
  () => counter.customer?.name,
  async (name) => {
    summary.value = null;
    if (!name || !store.showsCustomerBalance) return;
    summary.value = await api.getCustomerSummary(name).catch(() => null);
  },
  { immediate: true },
);

// ─── Payment choices ────────────────────────────────────────────────────
const paymentModes = ref<PaymentMode[]>([]);
const invoiceOptions = ref<InvoiceOption[]>([]);
const applicableOptions = computed(() => invoiceOptions.value.filter((o) => invoiceOptionApplies(o, counter.markAsPaid, counter.modeOfPayment)));

function setPayment(markAsPaid: boolean, mode: string, option: string | null) {
  if (!store.canCreditSale) markAsPaid = true;
  counter.setPayment(markAsPaid, mode, option);
  // Keep the option on one that fits: the profile default, else the only one.
  const opts = applicableOptions.value;
  if (invoiceOptions.value.length && !(counter.invoiceOption && opts.some((o) => o.name === counter.invoiceOption))) {
    counter.setPayment(markAsPaid, mode, opts.find((o) => o.is_default)?.name ?? (opts.length === 1 ? opts[0].name : null));
  }
}

async function loadChoices() {
  const [modes, options] = await Promise.all([
    api.getPaymentModes().catch(() => [] as PaymentMode[]),
    store.capabilities.can_invoice || store.isManager ? api.listInvoiceOptions().catch(() => [] as InvoiceOption[]) : Promise.resolve([] as InvoiceOption[]),
  ]);
  paymentModes.value = modes;
  invoiceOptions.value = options;
  const mode = counter.modeOfPayment && modes.some((m) => m.name === counter.modeOfPayment)
    ? counter.modeOfPayment
    : store.driverConfig?.default_cash_mode && modes.some((m) => m.name === store.driverConfig?.default_cash_mode)
      ? store.driverConfig.default_cash_mode
      : modes[0]?.name || '';
  setPayment(counter.markAsPaid, mode, counter.invoiceOption);
}

// ─── Lines ──────────────────────────────────────────────────────────────
function onAdd(item: CounterItem, qty: number, rate: number) {
  if (!counter.customer) {
    toast.warning('Pick a customer first');
    focusCustomer();
    return;
  }
  if (!allowWithoutStock.value && item.is_stock_item && item.actual_qty !== null && item.actual_qty <= 0) {
    toast.error(`${item.item_name} is out of stock`, { message: 'Your profile does not allow selling without stock.' });
    return;
  }
  counter.addLine(item, qty, rate);
}

const parseNum = (v: string) => Number(String(v).replace(/[^0-9.]/g, '')) || 0;

function onDiscount(raw: string) {
  let v = parseNum(raw);
  if (counter.discountMode === 'percent') {
    v = Math.min(Math.max(v, 0), 100);
    if (store.maxDiscountPercent > 0 && v > store.maxDiscountPercent) {
      v = store.maxDiscountPercent;
      toast.warning(`Discount capped at ${store.maxDiscountPercent}%`);
    }
  }
  counter.setDiscount(counter.discountMode, v);
}

function onLineKeydown(e: KeyboardEvent, uid: string, idx: number) {
  if (e.key === 'Enter') {
    e.preventDefault();
    (e.target as HTMLInputElement).blur();
    focusEntry();
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    counter.removeLine(uid);
    nextTick(() => {
      const next = counter.lines[Math.min(idx, counter.lines.length - 1)];
      if (next) qtyRefs.get(next.uid)?.focus();
      else focusEntry();
    });
  } else if (e.key === 'ArrowUp' && idx > 0) {
    e.preventDefault();
    qtyRefs.get(counter.lines[idx - 1].uid)?.focus();
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    const next = counter.lines[idx + 1];
    if (next) qtyRefs.get(next.uid)?.focus();
    else focusEntry();
  }
}

function focusLastLine() {
  const last = counter.lines[counter.lines.length - 1];
  if (last) qtyRefs.get(last.uid)?.focus();
}
function focusEntry() {
  nextTick(() => entryRow.value?.focus());
}
function focusCustomer() {
  nextTick(() => customerBox.value?.focus());
}

// ─── Actions ────────────────────────────────────────────────────────────
const busy = ref<'' | 'hold' | 'order' | 'invoice'>('');
const lastInvoice = ref<string | null>(null);
const canSubmit = computed(() => !!counter.customer && counter.hasLines && !shift.needsShift && !preview.value?.error);

function startNext() {
  counter.reset(defaultCustomer.value);
  preview.value = null;
  entryRow.value?.reset();
  if (counter.customer) focusEntry();
  else focusCustomer();
}

async function hold() {
  if (!canSubmit.value || busy.value) return;
  busy.value = 'hold';
  try {
    const today = isoToday();
    const items = counter.lines.map((l) => ({
      item_code: l.item.item_code,
      item_name: l.item.item_name,
      qty: l.qty,
      rate: l.rate,
      amount: l.qty * l.rate,
      delivery_date: today,
      stock_uom: l.item.stock_uom,
      price_list_rate: l.rate,
    }));
    const cart = cartPayload();
    const payload = { customer: cart.customer, items, discountPercent: cart.discountPercent, discountAmount: cart.discountAmount };
    const name = counter.orderName
      ? (await api.updateSalesOrder(counter.orderName, payload), counter.orderName)
      : (await api.createSalesOrder(payload)).name;
    toast.success(`Held as ${name}`, { message: 'Resume it from the Held list.' });
    startNext();
    loadQueue();
    queuePanel.value?.show('held');
  } catch (e: any) {
    toast.error('Could not hold the sale', { message: e?.message });
  } finally {
    busy.value = '';
  }
}

async function submit(withInvoice: boolean) {
  if (!canSubmit.value || busy.value) return;
  if (withInvoice && counter.markAsPaid && !counter.modeOfPayment) {
    toast.warning('Select a mode of payment');
    return;
  }
  let allowWithoutStock = false;
  const short = preview.value?.short_items || [];
  if (withInvoice && short.length) {
    const list = short.map((r) => `${r.item_name}: need ${qtyFmt(r.required_qty)}, have ${qtyFmt(r.available_qty)} ${r.stock_uom}`).join('\n');
    if (!preview.value?.allow_sale_without_stock) {
      toast.error('Not enough stock', { message: list, duration: 8000 });
      return;
    }
    allowWithoutStock = await confirm({
      title: 'Not enough stock for every line',
      message: `${list}\n\nInvoice anyway? What is in stock is delivered now; the rest stays pending on the order.`,
      confirmLabel: 'Invoice anyway',
      tone: 'warning',
      icon: 'alert',
    });
    if (!allowWithoutStock) return;
  }
  busy.value = withInvoice ? 'invoice' : 'order';
  try {
    const result = await api.createCounterSale(cartPayload(), {
      ...paymentPayload(),
      orderName: counter.orderName,
      invoice: withInvoice,
      allowWithoutStock,
    });
    if (result.invoice) {
      lastInvoice.value = result.invoice;
      const total = `${currency.value} ${money(result.rounded_total || result.grand_total)}`;
      toast.success(`Invoice ${result.invoice} · ${total}`, {
        message: result.short_items.length ? 'Available stock delivered; the rest is pending on the order.' : counter.markAsPaid ? `Paid by ${counter.modeOfPayment}` : 'Credit invoice',
        action: { label: 'Print', run: () => print('Sales Invoice', result.invoice!) },
        duration: 8000,
      });
      if (counter.autoPrint && printsDirectly('Sales Invoice')) void print('Sales Invoice', result.invoice);
    } else {
      toast.success(`Order ${result.order} submitted`, {
        action: { label: 'View', run: () => router.push({ name: 'order', params: { name: result.order } }) },
        duration: 6000,
      });
    }
    startNext();
    loadQueue();
  } catch (e: any) {
    toast.error(withInvoice ? 'Could not invoice the sale' : 'Could not submit the order', { message: e?.message, duration: 8000 });
  } finally {
    busy.value = '';
  }
}

function printLast() {
  if (lastInvoice.value) print('Sales Invoice', lastInvoice.value);
}

async function clear() {
  if (counter.hasLines) {
    const ok = await confirm({
      title: counter.orderName ? `Stop editing ${counter.orderName}?` : 'Clear this sale?',
      message: counter.orderName ? 'The held order is kept as it was saved.' : 'All lines will be removed.',
      confirmLabel: 'Clear',
      tone: 'danger',
      icon: 'trash',
    });
    if (!ok) return;
  }
  startNext();
}

// ─── Queue ──────────────────────────────────────────────────────────────
const queue = ref<CounterQueueData | null>(null);
const queueLoading = ref(false);
async function loadQueue() {
  queueLoading.value = true;
  try {
    queue.value = await api.getCounterQueue();
  } catch (_e) {
    /* the panel keeps what it had */
  } finally {
    queueLoading.value = false;
  }
}

async function resume(row: CounterQueueOrder) {
  if (busy.value) return;
  if (counter.hasLines && !(await confirm({ title: 'Replace the current lines?', message: `The sale being keyed in is dropped and ${row.name} is loaded instead.`, confirmLabel: 'Load', tone: 'warning' }))) return;
  try {
    const order = await api.getSalesOrder(row.name);
    counter.loadOrder(
      order.name,
      { name: order.customer, customer_name: order.customer_name, customer_group: '', territory: '' },
      order.items || [],
      { percent: order.additional_discount_percentage || 0, amount: order.discount_amount || 0 },
    );
    focusEntry();
  } catch (e: any) {
    toast.error('Could not load the order', { message: e?.message });
  }
}

const sheetOrder = ref<SalesOrder | null>(null);
const sheetOpen = ref(false);
async function openInvoiceSheet(row: CounterQueueOrder) {
  try {
    sheetOrder.value = await api.getSalesOrder(row.name);
    sheetOpen.value = true;
  } catch (e: any) {
    toast.error('Could not open the order', { message: e?.message });
  }
}
function onSheetInvoiced(invoiceName: string, deferredNote: string) {
  sheetOpen.value = false;
  lastInvoice.value = invoiceName;
  toast.success(`Invoice ${invoiceName} created`, { message: deferredNote || undefined, action: { label: 'Print', run: () => print('Sales Invoice', invoiceName) }, duration: 8000 });
  if (counter.autoPrint && printsDirectly('Sales Invoice')) void print('Sales Invoice', invoiceName);
  loadQueue();
  focusEntry();
}

// ─── Keyboard ───────────────────────────────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  if (document.querySelector('[role="dialog"]')) return; // a sheet or confirm owns the keys
  switch (e.key) {
    case 'F2':
      e.preventDefault();
      focusCustomer();
      break;
    case 'F3':
      e.preventDefault();
      focusEntry();
      break;
    case 'F4':
      e.preventDefault();
      discountInput.value?.focus();
      break;
    case 'F7':
      e.preventDefault();
      hold();
      break;
    case 'F8':
      e.preventDefault();
      submit(false);
      break;
    case 'F9':
      e.preventDefault();
      submit(true);
      break;
    case 'F10':
      e.preventDefault();
      printLast();
      break;
    case 'Escape':
      // Inputs with something to cancel stop the event themselves (see the entry row).
      if (counter.hasLines || counter.customer) clear();
      break;
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown);
  shift.refresh();
  if (!counter.customer && defaultCustomer.value) counter.setCustomer(defaultCustomer.value);
  await loadChoices();
  loadQueue();
  schedulePreview();
  if (counter.customer) focusEntry();
  else focusCustomer();
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  window.clearTimeout(previewTimer);
});

</script>
