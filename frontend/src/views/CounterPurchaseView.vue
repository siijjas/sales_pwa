<template>
  <div class="flex min-h-dvh flex-col px-3 pb-4 pt-safe md:px-5 xl:h-dvh xl:min-h-0">
    <!-- Header -->
    <div class="flex flex-wrap items-end justify-between gap-3 pb-3 pt-4 md:pt-5">
      <div class="min-w-0">
        <div class="flex items-center gap-3">
          <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-primary">Counter</p>
          <CounterModeTabs />
        </div>
        <h1 class="truncate text-[22px] font-bold leading-tight tracking-tight text-foreground md:text-[26px]">
          {{ cart.orderName ? `Editing ${cart.orderName}` : 'New purchase' }}
        </h1>
        <p class="mt-0.5 truncate text-[12.5px] text-muted">
          Receives into {{ ctx?.warehouse || '…' }}<template v-if="ctx?.price_list"> · {{ ctx.price_list }}</template><template v-if="ctx?.taxes_and_charges"> · {{ ctx.taxes_and_charges }}</template>
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <AppButton size="sm" variant="subtle" icon="save" :loading="busy === 'hold'" :disabled="!canSubmit || !!busy" @click="hold">Hold <kbd class="ml-1 text-[11px] opacity-70">F7</kbd></AppButton>
        <AppButton size="sm" variant="ghost" icon="trash" :disabled="!cart.hasLines && !cart.supplier" @click="clear">Clear <kbd class="ml-1 text-[11px] opacity-70">Esc</kbd></AppButton>
      </div>
    </div>

    <CounterShiftBar ref="shiftBar" class="mb-3" :currency="currency" @expense="expenseOpen = true" />

    <div class="grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1fr)_23rem]">
      <!-- ─── Left: supplier and lines ───────────────────────────────── -->
      <div class="flex min-h-0 flex-col gap-3">
        <AppCard padding="sm">
          <CustomerBox
            ref="supplierBox"
            :model-value="cart.supplier"
            :search="findSuppliers"
            icon="truck"
            noun="supplier"
            placeholder="Supplier: type a name, ID or mobile"
            @update:model-value="cart.setSupplier"
            @picked="focusEntry"
          />
        </AppCard>

        <AppCard padding="none" class="flex min-h-[20rem] flex-1 flex-col xl:min-h-0">
          <div class="relative z-20 border-b border-line bg-elevated p-2.5">
            <ItemEntryRow ref="entryRow" :customer="null" :search="findItems" :currency="currency" allow-rate allow-without-stock @add="onAdd" @down="focusFirstLine" />
          </div>
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
                  <th class="w-24 px-2 py-2 text-right" title="In the warehouse now">In stock</th>
                  <th class="w-10 px-2 py-2"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-if="!cart.lines.length">
                  <td colspan="8" class="px-4 py-10 text-center text-[13.5px] text-muted">
                    No lines yet. Type an item code or name above, the quantity and the supplier's rate, and press Enter.
                  </td>
                </tr>
                <tr v-for="(line, idx) in cart.lines" :key="line.uid" class="group">
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
                      @change="cart.setQty(line.uid, parseNum(($event.target as HTMLInputElement).value))"
                      @keydown="onLineKeydown($event, line.uid, idx)"
                    />
                  </td>
                  <td class="px-2 py-1.5 text-[12.5px] text-muted">{{ line.item.stock_uom }}</td>
                  <td class="px-2 py-1.5 text-right">
                    <input
                      :value="money(line.rate)"
                      type="text"
                      inputmode="decimal"
                      class="field-inline w-full"
                      @focus="($event.target as HTMLInputElement).select()"
                      @change="cart.setRate(line.uid, parseNum(($event.target as HTMLInputElement).value))"
                      @keydown.enter.prevent="focusEntry"
                    />
                  </td>
                  <td class="tnum px-2 py-1.5 text-right font-bold text-foreground">{{ money(line.qty * line.rate) }}</td>
                  <td class="tnum px-2 py-1.5 text-right text-[12.5px] text-muted">{{ line.item.actual_qty !== null && line.item.is_stock_item ? qtyFmt(line.item.actual_qty) : '' }}</td>
                  <td class="px-2 py-1.5 text-right">
                    <button type="button" tabindex="-1" class="flex h-8 w-8 items-center justify-center rounded-full text-subtle opacity-0 transition hover:bg-danger/10 hover:text-danger focus:opacity-100 group-hover:opacity-100" aria-label="Remove line" @click="cart.removeLine(line.uid)">
                      <AppIcon name="trash" :size="15" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppCard>
      </div>

      <!-- ─── Right: totals, submit, queue ───────────────────────────── -->
      <div class="flex min-h-0 flex-col gap-3 xl:overflow-y-auto">
        <AppCard padding="sm" class="space-y-1.5">
          <AppAlert v-if="preview?.error" tone="danger" :message="preview.error" class="mb-2" />
          <DataRow label="Items" :value="`${cart.lines.length} · qty ${qtyFmt(cart.count)}`" />
          <DataRow label="Subtotal" :value="`${currency} ${money(preview && !preview.error ? preview.total : cart.subtotal)}`" />
          <DataRow v-for="tax in preview && !preview.error ? preview.taxes : []" :key="tax.description" :label="tax.included_in_print_rate ? `${tax.description} (incl.)` : tax.description" :value="`${currency} ${money(tax.tax_amount)}`" />
          <div class="flex items-end justify-between border-t border-line pt-2">
            <p class="text-[12px] font-bold uppercase tracking-wide text-muted">Total</p>
            <p class="tnum text-[28px] font-bold leading-none tracking-tight text-foreground" :class="previewLoading ? 'opacity-60' : ''">{{ currency }} {{ money(grandTotal) }}</p>
          </div>
        </AppCard>

        <AppButton size="lg" block icon="send" :loading="busy === 'order'" :disabled="!canSubmit || !!busy" @click="submitOrder">Submit purchase order <kbd class="ml-1 text-[11px] opacity-70">F12</kbd></AppButton>

        <PurchaseQueue ref="queuePanel" class="min-h-[14rem] flex-1" :queue="queue" :loading="queueLoading" :busy="!!busy" :currency="currency" @refresh="loadQueue" @resume="resume" @bill="billFromQueue" />
      </div>
    </div>

    <ExpenseSheet v-model="expenseOpen" :currency="currency" @recorded="shiftBar?.refresh()" />

    <!-- After the order: bill it and receive the stock now? Then how the supplier is paid. -->
    <BottomSheet
      v-model="wizardOpen"
      :title="wizard?.step === 'ask' ? `${wizard.order} submitted` : `Bill ${wizard?.order || ''}`"
      :subtitle="wizard ? `${wizard.supplierName} · ${currency} ${money(wizard.total)}` : ''"
    >
      <div v-if="wizard" class="space-y-4">
        <template v-if="wizard.step === 'ask'">
          <p class="text-[14px] text-foreground">Bill it now and receive the stock into {{ ctx?.warehouse || 'the warehouse' }}?</p>
          <div class="grid gap-2">
            <AppButton data-wizard-primary size="lg" block icon="file-text" @click="wizardNext">Yes, bill and receive <kbd class="ml-1 text-[11px] opacity-70">Enter</kbd></AppButton>
            <AppButton size="md" block variant="secondary" @click="wizardOpen = false">Not now <kbd class="ml-1 text-[11px] opacity-70">Esc</kbd></AppButton>
          </div>
          <p class="text-[12px] text-muted">An order left unbilled waits in the To bill list until the goods arrive.</p>
        </template>

        <template v-else>
          <FormField label="Supplier invoice no." :required="ctx?.bill_no_required" :hint="ctx?.bill_no_required ? 'The number on the supplier’s bill.' : 'Optional: the number on the supplier’s bill.'">
            <input ref="billNoInput" v-model="billNo" type="text" autocomplete="off" class="field-input !min-h-[2.875rem] text-[15px] font-semibold" placeholder="e.g. INV-2041" />
          </FormField>
          <SegmentedControl
            :model-value="cart.markAsPaid ? 'paid' : 'credit'"
            :options="[{ value: 'paid', label: 'Paid now' }, { value: 'credit', label: 'On credit' }]"
            @update:model-value="(v: string) => cart.setPayment(v === 'paid', cart.modeOfPayment)"
          />
          <FormField v-if="cart.markAsPaid" label="Paid from">
            <div class="grid gap-2 sm:grid-cols-2">
              <ChoiceCard v-for="m in paymentModes" :key="m.name" :selected="cart.modeOfPayment === m.name" :title="m.name" :subtitle="m.type" @click="cart.setPayment(true, m.name)" />
            </div>
          </FormField>
          <p class="text-[12px] text-muted">
            {{ cart.markAsPaid ? `The payment comes off ${cart.modeOfPayment || 'that mode'} on your shift's closing.` : 'The bill stays payable to the supplier.' }}
          </p>
          <AppAlert v-if="wizardError" tone="danger" :message="wizardError" />
          <AppButton data-wizard-primary size="lg" block icon="file-text" :loading="busy === 'bill'" :disabled="!canBill || !!busy" @click="wizardNext">
            Create bill <kbd class="ml-1 text-[11px] opacity-70">Enter</kbd>
          </AppButton>
        </template>
      </div>
    </BottomSheet>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as api from '../api/frappe';
import type { CounterItem, Customer, PaymentMode, PurchaseContext, PurchasePreview, PurchaseQueue as PurchaseQueueData, PurchaseQueueOrder } from '../types';
import { useSessionStore } from '../stores/session';
import { useCounterPurchaseStore } from '../stores/counterPurchase';
import { useToast } from '../composables/useToast';
import { useConfirm } from '../composables/useConfirm';
import { money, qty as qtyFmt } from '../utils/format';
import CustomerBox from '../components/counter/CustomerBox.vue';
import ItemEntryRow from '../components/counter/ItemEntryRow.vue';
import PurchaseQueue from '../components/counter/PurchaseQueue.vue';
import CounterShiftBar from '../components/counter/CounterShiftBar.vue';
import CounterModeTabs from '../components/counter/CounterModeTabs.vue';
import ExpenseSheet from '../components/counter/ExpenseSheet.vue';
import { AppAlert, AppButton, AppCard, AppIcon, BottomSheet, ChoiceCard, DataRow, FormField, SegmentedControl } from '../components/ui';

// The Counter's Purchase screen: a Purchase Order keyed in like a sale, then billed
// (receiving the stock) and paid from the drawer or left on credit. The server side
// is sales_pwa.sales_app.counter_purchase.

const store = useSessionStore();
const cart = useCounterPurchaseStore();
const toast = useToast();
const { confirm, state: confirmState } = useConfirm();

const supplierBox = ref<InstanceType<typeof CustomerBox> | null>(null);
const entryRow = ref<InstanceType<typeof ItemEntryRow> | null>(null);
const queuePanel = ref<InstanceType<typeof PurchaseQueue> | null>(null);
const shiftBar = ref<InstanceType<typeof CounterShiftBar> | null>(null);
const billNoInput = ref<HTMLInputElement | null>(null);
const qtyRefs = new Map<string, HTMLInputElement>();
const setQtyRef = (uid: string, el: HTMLInputElement | null) => (el ? qtyRefs.set(uid, el) : qtyRefs.delete(uid));

const currency = computed(() => store.currencyDisplay);
const ctx = ref<PurchaseContext | null>(null);
const expenseOpen = ref(false);

// The party box and the entry row take the purchase-side searches.
const findSuppliers = async (q: string, limit: number): Promise<Customer[]> =>
  (await api.searchSuppliers(q, limit)).map((s) => ({ name: s.name, customer_name: s.supplier_name, customer_group: s.supplier_group || '', territory: '', mobile_no: s.mobile_no }));
const findItems = (q: string, signal: AbortSignal) => api.searchPurchaseItems(q, cart.supplier?.name || null, 15, signal);

// ─── Preview: ERPNext's totals for the cart ─────────────────────────────
const preview = ref<PurchasePreview | null>(null);
const previewLoading = ref(false);
let previewTimer: number | undefined;
let previewSeq = 0;

const cartPayload = (): api.PurchaseCartPayload => ({
  supplier: cart.supplier!.name,
  items: cart.lines.map((l) => ({ item_code: l.item.item_code, qty: l.qty, rate: l.rate })),
});

function schedulePreview() {
  window.clearTimeout(previewTimer);
  if (!cart.supplier || !cart.lines.length) {
    preview.value = null;
    previewLoading.value = false;
    return;
  }
  previewLoading.value = true;
  const seq = ++previewSeq;
  previewTimer = window.setTimeout(async () => {
    try {
      const res = await api.previewCounterPurchase(cartPayload());
      if (seq === previewSeq) preview.value = res;
    } catch (e: any) {
      if (seq === previewSeq) preview.value = { ...(preview.value as PurchasePreview), error: e?.message || 'Could not compute totals' } as PurchasePreview;
    } finally {
      if (seq === previewSeq) previewLoading.value = false;
    }
  }, 250);
}
watch(() => [cart.supplier?.name, cart.lines.map((l) => `${l.item.item_code}:${l.qty}:${l.rate}`).join('|')], schedulePreview);

const grandTotal = computed(() => {
  const p = preview.value;
  if (!p || p.error) return cart.subtotal;
  return !p.disable_rounded_total && p.rounded_total > 0 ? p.rounded_total : p.grand_total;
});

// ─── Lines ──────────────────────────────────────────────────────────────
function onAdd(item: CounterItem, qty: number, rate: number) {
  if (!cart.supplier) {
    toast.warning('Pick a supplier first');
    focusSupplier();
    return;
  }
  const line = cart.addLine(item, qty, rate);
  nextTick(() => qtyRefs.get(line.uid)?.scrollIntoView({ block: 'nearest' }));
}

const parseNum = (v: string) => Number(String(v).replace(/[^0-9.]/g, '')) || 0;

function onLineKeydown(e: KeyboardEvent, uid: string, idx: number) {
  if (e.key === 'Enter') {
    e.preventDefault();
    (e.target as HTMLInputElement).blur();
    focusEntry();
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    cart.removeLine(uid);
    nextTick(() => {
      const next = cart.lines[Math.min(idx, cart.lines.length - 1)];
      if (next) qtyRefs.get(next.uid)?.focus();
      else focusEntry();
    });
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (idx > 0) qtyRefs.get(cart.lines[idx - 1].uid)?.focus();
    else focusEntry();
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    const next = cart.lines[idx + 1];
    if (next) qtyRefs.get(next.uid)?.focus();
  }
}

function focusFirstLine() {
  const first = cart.lines[0];
  if (first) qtyRefs.get(first.uid)?.focus();
}
const focusEntry = () => nextTick(() => entryRow.value?.focus());
const focusSupplier = () => nextTick(() => supplierBox.value?.focus());
const focusStart = () => (cart.supplier ? focusEntry() : focusSupplier());

// ─── Actions ────────────────────────────────────────────────────────────
const busy = ref<'' | 'hold' | 'order' | 'bill'>('');
const canSubmit = computed(() => !!cart.supplier && cart.hasLines && !preview.value?.error);

function startNext(focus = true) {
  cart.reset();
  preview.value = null;
  entryRow.value?.reset();
  if (focus) focusStart();
}

async function hold() {
  if (!canSubmit.value || busy.value) return;
  busy.value = 'hold';
  try {
    const res = await api.createCounterPurchase(cartPayload(), { orderName: cart.orderName, hold: true });
    toast.success(`Held as ${res.order}`, { message: 'Resume it from the Held list.' });
    startNext();
    loadQueue();
    queuePanel.value?.show('held');
  } catch (e: any) {
    toast.error('Could not hold the purchase', { message: e?.message });
  } finally {
    busy.value = '';
  }
}

interface Wizard {
  order: string;
  supplierName: string;
  total: number;
  step: 'ask' | 'bill';
}
const wizard = ref<Wizard | null>(null);
const wizardOpen = ref(false);
const wizardError = ref('');
const billNo = ref('');
const canBill = computed(() => (!ctx.value?.bill_no_required || !!billNo.value.trim()) && (!cart.markAsPaid || !!cart.modeOfPayment));

const focusWizard = () =>
  nextTick(() => {
    (document.activeElement as HTMLElement | null)?.blur?.();
    window.setTimeout(() => {
      if (wizard.value?.step === 'bill' && billNoInput.value) billNoInput.value.focus();
      else (document.querySelector('[role="dialog"] [data-wizard-primary]') as HTMLElement | null)?.focus();
    }, 60);
  });

async function submitOrder() {
  if (!canSubmit.value || busy.value) return;
  busy.value = 'order';
  try {
    const res = await api.createCounterPurchase(cartPayload(), { orderName: cart.orderName });
    openWizard({ order: res.order, supplierName: res.supplier_name || res.supplier, total: res.rounded_total || res.grand_total, step: 'ask' });
    // The sheet owns the keyboard now; the next purchase's box takes focus when it closes.
    startNext(false);
    loadQueue();
    shiftBar.value?.refresh();
  } catch (e: any) {
    toast.error('Could not submit the purchase order', { message: e?.message, duration: 8000 });
  } finally {
    busy.value = '';
  }
}

function openWizard(w: Wizard) {
  wizard.value = w;
  wizardError.value = '';
  billNo.value = '';
  wizardOpen.value = true;
  focusWizard();
}

function billFromQueue(row: PurchaseQueueOrder) {
  if (busy.value) return;
  openWizard({ order: row.name, supplierName: row.supplier_name || row.supplier, total: row.grand_total, step: 'bill' });
}

async function wizardNext() {
  const w = wizard.value;
  if (!w || busy.value) return;
  wizardError.value = '';
  if (w.step === 'ask') {
    w.step = 'bill';
    focusWizard();
    return;
  }
  if (ctx.value?.bill_no_required && !billNo.value.trim()) {
    wizardError.value = 'Enter the supplier’s invoice number.';
    billNoInput.value?.focus();
    return;
  }
  if (cart.markAsPaid && !cart.modeOfPayment) {
    wizardError.value = 'Pick how the supplier is paid.';
    return;
  }
  busy.value = 'bill';
  try {
    const res = await api.billCounterPurchase(w.order, { markAsPaid: cart.markAsPaid, modeOfPayment: cart.modeOfPayment, billNo: billNo.value.trim() || null });
    wizardOpen.value = false;
    toast.success(`Bill ${res.invoice} · ${currency.value} ${money(res.rounded_total || res.grand_total)}`, {
      message: res.payment ? `Stock received · paid from ${cart.modeOfPayment} (${res.payment})` : 'Stock received · payable to the supplier',
      duration: 8000,
    });
    loadQueue();
    shiftBar.value?.refresh();
  } catch (e: any) {
    wizardError.value = e?.message || 'Could not create the bill';
  } finally {
    busy.value = '';
  }
}

watch(wizardOpen, (open) => {
  if (!open) {
    wizard.value = null;
    focusStart();
  }
});

async function clear() {
  if (cart.hasLines) {
    const ok = await confirm({
      title: cart.orderName ? `Stop editing ${cart.orderName}?` : 'Clear this purchase?',
      message: cart.orderName ? 'The held order is kept as it was saved.' : 'All lines will be removed.',
      confirmLabel: 'Clear',
      tone: 'danger',
      icon: 'trash',
    });
    if (!ok) return;
  }
  startNext();
}

// ─── Queue ──────────────────────────────────────────────────────────────
const queue = ref<PurchaseQueueData | null>(null);
const queueLoading = ref(false);
async function loadQueue() {
  queueLoading.value = true;
  try {
    queue.value = await api.getPurchaseQueue();
  } catch (_e) {
    /* the panel keeps what it had */
  } finally {
    queueLoading.value = false;
  }
}

async function resume(row: PurchaseQueueOrder) {
  if (busy.value) return;
  if (cart.hasLines && !(await confirm({ title: 'Replace the current lines?', message: `The purchase being keyed in is dropped and ${row.name} is loaded instead.`, confirmLabel: 'Load', tone: 'warning' }))) return;
  try {
    cart.loadOrder(await api.getCounterPurchase(row.name));
    focusEntry();
  } catch (e: any) {
    toast.error('Could not load the purchase order', { message: e?.message });
  }
}

// ─── Payment modes ──────────────────────────────────────────────────────
const paymentModes = ref<PaymentMode[]>([]);
async function loadChoices() {
  const [context, modes] = await Promise.all([api.getPurchaseContext().catch(() => null), api.getPaymentModes().catch(() => [] as PaymentMode[])]);
  ctx.value = context;
  paymentModes.value = modes;
  if (!modes.some((m) => m.name === cart.modeOfPayment)) {
    const drawer = store.driverConfig?.default_cash_mode;
    const mode = drawer && modes.some((m) => m.name === drawer) ? drawer : modes.find((m) => m.type === 'Cash')?.name || modes[0]?.name || '';
    cart.setPayment(cart.markAsPaid, mode);
  }
}

// ─── Keyboard ───────────────────────────────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  if (wizardOpen.value && !confirmState.pending) {
    const tag = (e.target as HTMLElement).tagName;
    if (e.key === 'Enter' && tag !== 'BUTTON') {
      e.preventDefault();
      wizardNext();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      wizardOpen.value = false;
    }
    return;
  }
  if (document.querySelector('[role="dialog"]')) return; // a sheet or confirm owns the keys
  switch (e.key) {
    case 'F2':
      e.preventDefault();
      focusSupplier();
      break;
    case 'F3':
      e.preventDefault();
      focusEntry();
      break;
    case 'F6':
      e.preventDefault();
      if (store.capabilities.can_record_expense && store.driverConfig) expenseOpen.value = true;
      break;
    case 'F7':
      e.preventDefault();
      hold();
      break;
    case 'F12':
      e.preventDefault();
      submitOrder();
      break;
    case 'Escape':
      if (cart.hasLines || cart.supplier) clear();
      break;
  }
}

watch(expenseOpen, (open) => !open && focusStart());

onMounted(async () => {
  window.addEventListener('keydown', onKeydown);
  await loadChoices();
  loadQueue();
  schedulePreview();
  focusStart();
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  window.clearTimeout(previewTimer);
});
</script>
