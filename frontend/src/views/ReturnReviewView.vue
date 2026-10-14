<template>
  <WorkspacePage back title="Review return" :subtitle="returns.customer ? `From ${returns.customer.customer_name}` : undefined">
    <template #actions>
      <AppButton v-if="returns.lines.length" variant="ghost" size="sm" icon="trash" @click="clearAll">Clear</AppButton>
    </template>

    <div class="space-y-4 pb-28">
      <AppCard padding="lg" class="bg-danger/10 ring-1 ring-inset ring-danger/25">
        <p class="text-[11px] font-bold uppercase tracking-[0.08em] text-danger">Credit to issue</p>
        <p class="tnum mt-1 text-[30px] font-semibold leading-none tracking-tightest text-foreground">{{ currency }} {{ money(returns.total) }}</p>
        <p class="mt-2 text-[12.5px] text-muted">{{ plural(returns.lines.length, 'item') }} · {{ qty(returns.count) }} units · reduces the customer's outstanding balance</p>
      </AppCard>

      <AppAlert v-if="error" tone="danger" :message="error" />

      <AppCard v-if="returns.lines.length" padding="none" class="divide-y divide-line">
        <div v-for="line in returns.lines" :key="line.item.item_code" class="flex items-center justify-between gap-3 p-4">
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold leading-tight text-foreground">{{ line.item.item_name }}</p>
            <p class="mt-0.5 text-xs text-muted">{{ line.item.item_code }}</p>
            <p class="tnum mt-1 text-sm font-bold text-foreground">
              {{ currency }} {{ money(line.qty * lineRate(line)) }}
              <span class="font-medium text-muted">· {{ qty(line.qty) }} × {{ money(lineRate(line)) }}</span>
            </p>
          </div>
          <QtyStepper :model-value="line.qty" @change="(d: number) => returns.changeQty(line.item.item_code, d)" />
        </div>
      </AppCard>
      <EmptyState v-else icon="rotate-ccw" title="No items selected" description="Add the items being returned first.">
        <template #action>
          <AppButton variant="secondary" icon="package" @click="router.replace({ name: 'return-items', params: { name } })">Choose items</AppButton>
        </template>
      </EmptyState>
    </div>

    <StickyBar v-if="returns.lines.length">
      <AppButton variant="danger" size="lg" block icon="rotate-ccw" :loading="submitting" @click="submit">
        {{ submitting ? 'Issuing…' : `Issue credit note · ${currency} ${money(returns.total)}` }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import { useReturnStore } from '../stores/returns';
import { useShiftStore } from '../stores/shift';
import { lineRate } from '../stores/sale';
import { useToast } from '../composables/useToast';
import { usePrint } from '../composables/usePrint';
import { useConfirm } from '../composables/useConfirm';
import { money, plural, qty } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, QtyStepper, EmptyState, StickyBar } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const returns = useReturnStore();
const shift = useShiftStore();
const toast = useToast();
const { print } = usePrint();
const { confirm } = useConfirm();

const name = computed(() => String(route.params.name));
const currency = computed(() => store.currencyDisplay);
const submitting = ref(false);
const error = ref('');

onMounted(async () => {
  await shift.refresh();
  if (shift.needsShift) {
    router.replace(shift.gateRoute);
    return;
  }
  // The review belongs to the customer in the route; a stale draft for someone else is dropped.
  if (returns.customer && returns.customer.name !== name.value) returns.clear();
  if (!returns.customer) router.replace({ name: 'return-items', params: { name: name.value } });
});

async function clearAll() {
  if (await confirm({ title: 'Clear the return?', message: 'All selected items will be removed.', confirmLabel: 'Clear', tone: 'danger', icon: 'trash' })) {
    returns.clear();
    router.replace({ name: 'return-items', params: { name: name.value } });
  }
}

const submit = async () => {
  if (!returns.customer || !returns.lines.length) return;
  submitting.value = true;
  error.value = '';
  try {
    // Send the rate the driver was shown — the server only sees the price list otherwise.
    const items = returns.lines.map((line) => ({ item_code: line.item.item_code, qty: line.qty, rate: lineRate(line) }));
    const total = returns.total;
    const creditNote = await api.createSalesReturn(returns.customer.name, items);
    const customer = returns.customer.name;
    returns.clear();
    toast.success(`Credit note ${creditNote} issued`, {
      message: `${currency.value} ${money(total)} credited`,
      action: { label: 'Print', run: () => print('Sales Invoice', creditNote, { isReturn: true }) },
      duration: 8000,
    });
    router.replace({ name: 'customer', params: { name: customer } });
  } catch (e: any) {
    error.value = e?.message || 'Failed to process the return. Check permissions and stock settings.';
  } finally {
    submitting.value = false;
  }
};
</script>
