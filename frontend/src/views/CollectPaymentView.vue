<template>
  <WorkspacePage back title="Collect payment" :subtitle="customer?.customer_name">
    <template #actions>
      <AppButton variant="ghost" size="sm" icon="refresh" :loading="loading" aria-label="Refresh" @click="reload" />
    </template>

    <SkeletonList v-if="loading && !customer" :rows="3" height="5rem" />
    <AppAlert v-else-if="loadError" tone="danger" :message="loadError" />

    <div v-else-if="customer" class="space-y-5 pb-28">
      <!-- Customer summary -->
      <AppCard padding="sm">
        <div class="flex items-center gap-3">
          <Avatar :name="customer.customer_name" />
          <div class="min-w-0 flex-1">
            <p class="truncate font-bold text-foreground">{{ customer.customer_name }}</p>
            <p class="truncate text-xs text-muted">{{ customer.name }}</p>
          </div>
          <div v-if="showBalance && summary" class="shrink-0 text-right">
            <p class="text-[10px] font-bold uppercase tracking-wide text-muted">Outstanding</p>
            <p class="tnum text-[15px] font-bold text-foreground">{{ currency }} {{ money(summary.outstanding_balance) }}</p>
          </div>
        </div>
      </AppCard>

      <!-- Amount + mode -->
      <AppCard class="space-y-4">
        <FormField label="Amount received" required>
          <BaseInput v-model="paidAmount" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" min="0" step="0.01" @update:model-value="onPaidAmountChange" />
        </FormField>
        <div>
          <p class="mb-[7px] text-[13px] font-semibold text-foreground">Mode of payment <span class="text-danger">*</span></p>
          <div v-if="paymentModes.length <= 4" class="flex flex-wrap gap-2">
            <button
              v-for="mode in paymentModes"
              :key="mode.name"
              type="button"
              class="focus-ring rounded-full px-4 py-2 text-[13px] font-semibold ring-1 ring-inset transition"
              :class="modeOfPayment === mode.name ? 'bg-primary text-primary-fg ring-primary' : 'bg-card text-foreground ring-line-strong hover:bg-card-muted'"
              @click="modeOfPayment = mode.name"
            >
              {{ mode.name }}
            </button>
          </div>
          <BaseSelect v-else v-model="modeOfPayment" placeholder="Select mode">
            <option v-for="mode in paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
          </BaseSelect>
        </div>
      </AppCard>

      <!-- Allocation -->
      <section class="space-y-2">
        <SectionHeader title="Allocate to" />
        <SegmentedControl
          :model-value="allocationMode"
          :options="[{ value: 'auto', label: 'Oldest first' }, { value: 'manual', label: 'Pick invoices' }, { value: 'advance', label: 'Advance' }]"
          @update:model-value="(v: string) => (allocationMode = v as AllocationMode)"
        />
        <p class="px-0.5 text-xs text-muted">
          {{ allocationMode === 'auto' ? 'The amount settles the oldest invoices first.' : allocationMode === 'manual' ? 'Choose which invoices this payment settles and how much goes to each.' : 'Recorded as an advance, not allocated to any invoice.' }}
        </p>
      </section>

      <!-- Invoices -->
      <section v-if="allocationMode !== 'advance'" class="space-y-2.5">
        <div class="flex items-center justify-between px-0.5">
          <p class="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">Outstanding invoices</p>
          <span class="tnum text-xs font-semibold" :class="unallocatedAmount < -0.005 ? 'text-danger' : 'text-muted'">
            Unallocated {{ currency }} {{ money(unallocatedAmount) }}
          </span>
        </div>
        <SearchBar v-if="allocationMode === 'manual' && invoices.length > 5" v-model="invoiceSearch" placeholder="Search invoice number…" />
        <SkeletonList v-if="loadingInvoices" :rows="2" height="4rem" />
        <EmptyState v-else-if="!invoices.length" icon="file-text" title="No outstanding invoices" description="Record the amount as an advance instead." />
        <div v-else class="space-y-2">
          <div
            v-for="inv in filteredInvoices"
            :key="inv.name"
            class="rounded-2xl bg-card p-3.5 ring-1 ring-inset transition"
            :class="inv.checked ? 'bg-primary/[0.05] ring-primary/50' : 'ring-line'"
          >
            <div class="flex items-start gap-3" :class="allocationMode === 'manual' ? 'cursor-pointer' : ''" @click="allocationMode === 'manual' && toggleInvoice(inv)">
              <span
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition"
                :class="inv.checked ? 'border-primary bg-primary text-primary-fg' : 'border-line-strong'"
              >
                <AppIcon v-if="inv.checked" name="check" :size="12" :stroke-width="3.5" />
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="truncate text-[15px] font-semibold text-foreground">{{ inv.name }}</p>
                    <p class="text-xs text-muted">{{ shortDate(inv.posting_date) }}<span v-if="inv.outstanding_amount < inv.grand_total - 0.005"> · of {{ money(inv.grand_total) }}</span></p>
                  </div>
                  <div class="shrink-0 text-right">
                    <p class="text-[10px] font-bold uppercase tracking-wide text-muted">Pending</p>
                    <p class="tnum text-[15px] font-bold text-foreground">{{ money(inv.outstanding_amount) }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="inv.checked" class="mt-3 flex items-center justify-between border-t border-line pt-2.5">
              <span class="text-xs font-semibold text-muted">Allocated</span>
              <input
                v-if="allocationMode === 'manual'"
                v-model.number="inv.allocated_amount"
                type="number"
                inputmode="decimal"
                min="0"
                :max="inv.outstanding_amount"
                step="0.01"
                class="field-inline"
                @click.stop
                @input="validateAllocation(inv)"
              />
              <span v-else class="tnum text-sm font-bold text-primary">{{ currency }} {{ money(inv.allocated_amount) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Advance: optional order link -->
      <section v-else class="space-y-2.5">
        <SectionHeader title="Link to an order" description="Optional. Leave unlinked for a general advance." />
        <SearchBar v-if="!loadingSalesOrders && salesOrders.length > 5" v-model="orderSearch" placeholder="Search order number…" />
        <SkeletonList v-if="loadingSalesOrders" :rows="2" height="4rem" />
        <div v-else class="space-y-2">
          <ChoiceCard title="No order" subtitle="General advance payment" :selected="selectedSalesOrder === null" @click="selectedSalesOrder = null" />
          <ChoiceCard
            v-for="so in filteredSalesOrders"
            :key="so.name"
            :title="so.name"
            :subtitle="`${shortDate(so.transaction_date)} · ${currency} ${money(so.grand_total)}`"
            :selected="selectedSalesOrder === so.name"
            @click="selectedSalesOrder = so.name"
          >
            <template #trailing>
              <div class="shrink-0 text-right">
                <p class="text-[10px] font-bold uppercase tracking-wide text-muted">Pending</p>
                <p class="tnum text-sm font-bold text-primary">{{ money(so.grand_total - (so.advance_paid || 0)) }}</p>
              </div>
            </template>
          </ChoiceCard>
        </div>
      </section>

      <AppAlert v-if="submitError" tone="danger" :message="submitError" />
    </div>

    <StickyBar v-if="customer">
      <AppButton size="lg" block icon="check" :disabled="!isValid" :loading="submitting" @click="submit">
        {{ submitting ? 'Recording…' : `Confirm payment${amountNumber > 0 ? ` · ${currency} ${money(amountNumber)}` : ''}` }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { Customer, CustomerSummary, OutstandingInvoice, PaymentMode, PaymentReference, SalesOrderSummary } from '../types';
import { useSessionStore } from '../stores/session';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { money, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, Avatar, BaseInput, BaseSelect, ChoiceCard, FormField, SearchBar, SectionHeader, SegmentedControl, SkeletonList, EmptyState, StickyBar } from '../components/ui';

type AllocationMode = 'auto' | 'manual' | 'advance';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const shift = useShiftStore();
const toast = useToast();

const name = computed(() => String(route.params.name));
const currency = computed(() => store.currencyDisplay);
// Sales Profile.show_customer_balance off: staff never see what the customer owes.
const showBalance = computed(() => store.showsCustomerBalance);

const customer = ref<Customer | null>(null);
const summary = ref<CustomerSummary | null>(null);
const paymentModes = ref<PaymentMode[]>([]);
const invoices = ref<OutstandingInvoice[]>([]);
const salesOrders = ref<SalesOrderSummary[]>([]);
const loading = ref(true);
const loadError = ref('');
const loadingInvoices = ref(false);
const loadingSalesOrders = ref(false);

const paidAmount = ref<number | string>('');
const modeOfPayment = ref('');
const allocationMode = ref<AllocationMode>('auto');
const selectedSalesOrder = ref<string | null>(null);
const invoiceSearch = ref('');
const orderSearch = ref('');
const submitting = ref(false);
const submitError = ref('');

const amountNumber = computed(() => Number(paidAmount.value) || 0);

onMounted(async () => {
  await shift.refresh();
  if (shift.needsShift) {
    toast.warning(shift.isStale ? 'Close your previous shift first' : 'Open your shift first', { message: 'Payments need an open shift.' });
    router.replace(shift.gateRoute);
    return;
  }
  try {
    customer.value = await api.getCustomer(name.value);
  } catch (e: any) {
    loadError.value = e?.message || 'Customer not found';
    loading.value = false;
    return;
  }
  loading.value = false;
  api
    .getPaymentModes()
    .then((modes) => {
      paymentModes.value = modes;
      if (modes.length && !modeOfPayment.value) modeOfPayment.value = modes[0].name;
    })
    .catch(() => {});
  await reload();
});

async function reload() {
  await Promise.all([loadInvoices(), loadSalesOrders(), loadSummary()]);
}

async function loadInvoices() {
  loadingInvoices.value = true;
  try {
    const data = await api.getOutstandingInvoices(name.value);
    invoices.value = data.map((inv) => ({ ...inv, checked: false, allocated_amount: 0 }));
    if (allocationMode.value === 'auto') autoAllocate();
  } catch (_e) {
    invoices.value = [];
  } finally {
    loadingInvoices.value = false;
  }
}

async function loadSalesOrders() {
  loadingSalesOrders.value = true;
  try {
    salesOrders.value = await api.getSalesOrders(name.value);
  } catch (_e) {
    salesOrders.value = [];
  } finally {
    loadingSalesOrders.value = false;
  }
}

async function loadSummary() {
  if (!showBalance.value) return;
  try {
    summary.value = await api.getCustomerSummary(name.value);
  } catch (_e) {
    summary.value = null;
  }
}

// ── Allocation ────────────────────────────────────────────────────────────
const onPaidAmountChange = () => {
  if (allocationMode.value === 'auto') autoAllocate();
};

const autoAllocate = () => {
  if (amountNumber.value <= 0) {
    invoices.value.forEach((inv) => {
      inv.checked = false;
      inv.allocated_amount = 0;
    });
    return;
  }
  let remaining = amountNumber.value;
  const sorted = [...invoices.value].sort((a, b) => new Date(a.posting_date).getTime() - new Date(b.posting_date).getTime());
  sorted.forEach((inv) => {
    if (remaining <= 0) {
      inv.checked = false;
      inv.allocated_amount = 0;
    } else {
      const toAllocate = Math.min(remaining, inv.outstanding_amount);
      inv.checked = toAllocate > 0;
      inv.allocated_amount = toAllocate;
      remaining -= toAllocate;
    }
  });
};

const toggleInvoice = (inv: OutstandingInvoice) => {
  inv.checked = !inv.checked;
  if (inv.checked) {
    if (!inv.allocated_amount) inv.allocated_amount = inv.outstanding_amount;
  } else {
    inv.allocated_amount = 0;
  }
  updatePaidAmountFromSelection();
};

const validateAllocation = (inv: OutstandingInvoice) => {
  if (inv.allocated_amount && inv.allocated_amount > inv.outstanding_amount) inv.allocated_amount = inv.outstanding_amount;
  if (inv.allocated_amount && inv.allocated_amount < 0) inv.allocated_amount = 0;
  if (inv.allocated_amount === 0) inv.checked = false;
  updatePaidAmountFromSelection();
};

const updatePaidAmountFromSelection = () => {
  paidAmount.value = invoices.value.filter((i) => i.checked).reduce((sum, i) => sum + (i.allocated_amount || 0), 0);
};

const allocatedTotal = computed(() => invoices.value.filter((i) => i.checked).reduce((sum, i) => sum + (i.allocated_amount || 0), 0));
const unallocatedAmount = computed(() => amountNumber.value - allocatedTotal.value);

const filteredInvoices = computed(() => {
  const q = invoiceSearch.value.trim().toLowerCase();
  return q ? invoices.value.filter((inv) => inv.name.toLowerCase().includes(q)) : invoices.value;
});
const filteredSalesOrders = computed(() => {
  const q = orderSearch.value.trim().toLowerCase();
  return q ? salesOrders.value.filter((so) => so.name.toLowerCase().includes(q)) : salesOrders.value;
});

const isValid = computed(() => {
  if (!customer.value || !modeOfPayment.value || amountNumber.value <= 0) return false;
  if (allocationMode.value === 'advance') return true;
  return unallocatedAmount.value >= -0.005;
});

watch(allocationMode, (mode) => {
  if (mode === 'auto') autoAllocate();
  else if (mode === 'advance') {
    invoices.value.forEach((inv) => {
      inv.checked = false;
      inv.allocated_amount = 0;
    });
  }
});

// ── Submit ────────────────────────────────────────────────────────────────
const submit = async () => {
  if (!isValid.value || !customer.value) return;
  submitting.value = true;
  submitError.value = '';
  try {
    const references: PaymentReference[] =
      allocationMode.value === 'advance'
        ? []
        : invoices.value
            .filter((i) => i.checked && (i.allocated_amount || 0) > 0)
            .map((i) => ({ name: i.name, grand_total: i.grand_total, outstanding_amount: i.outstanding_amount, allocated_amount: i.allocated_amount || 0 }));
    const entry = await api.createPaymentEntry(
      customer.value.name,
      modeOfPayment.value,
      amountNumber.value,
      references,
      allocationMode.value === 'advance' ? selectedSalesOrder.value || undefined : undefined,
    );
    toast.success(`Payment ${entry} recorded`, { message: `${currency.value} ${money(amountNumber.value)} by ${modeOfPayment.value}` });
    router.replace({ name: 'customer', params: { name: customer.value.name } });
  } catch (e: any) {
    submitError.value = e?.message || 'Failed to record the payment';
  } finally {
    submitting.value = false;
  }
};
</script>
