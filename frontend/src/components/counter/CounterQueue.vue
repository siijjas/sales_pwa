<template>
  <AppCard padding="none" class="flex min-h-0 flex-col">
    <div class="flex items-center gap-1 border-b border-line p-2">
      <button
        v-for="t in TABS"
        :key="t.key"
        type="button"
        tabindex="-1"
        class="focus-ring flex-1 rounded-xl px-2 py-2 text-[12.5px] font-semibold transition"
        :class="tab === t.key ? 'bg-primary-soft text-primary' : 'text-muted hover:bg-card-muted hover:text-foreground'"
        @click="tab = t.key"
      >
        {{ t.label }} <span class="tnum">{{ counts[t.key] }}</span>
      </button>
      <button type="button" tabindex="-1" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-subtle transition hover:bg-card-muted hover:text-foreground" aria-label="Refresh" @click="$emit('refresh')">
        <AppIcon name="refresh" :size="16" :class="loading ? 'animate-spin' : ''" />
      </button>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <template v-if="tab === 'held'">
        <EmptyState v-if="!queue?.held.length" icon="save" title="Nothing on hold" description="F7 parks the sale being keyed in so you can take the next one." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.held" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.customer_name || row.customer }}</p>
              <p class="truncate text-[12px] text-muted">{{ row.name }} · {{ time(row.modified) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span></p>
            </div>
            <AppButton size="sm" variant="secondary" icon="edit" tabindex="-1" :disabled="busy" @click="$emit('resume', row)">Resume</AppButton>
          </div>
        </div>
      </template>

      <template v-else-if="tab === 'to_invoice'">
        <EmptyState v-if="!queue?.to_invoice.length" icon="file-text" title="Nothing to invoice" description="Orders you submit without an invoice wait here." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.to_invoice" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.customer_name || row.customer }}</p>
              <p class="truncate text-[12px] text-muted">{{ row.name }} · {{ shortDate(row.transaction_date) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span></p>
            </div>
            <AppButton
              v-if="editable(row)"
              size="sm"
              variant="secondary"
              icon="edit"
              tabindex="-1"
              :disabled="busy"
              :aria-label="`Edit ${row.name}`"
              @click="$emit('edit', row)"
            >
              Edit
            </AppButton>
            <AppButton size="sm" icon="file-text" tabindex="-1" :disabled="busy" @click="$emit('invoice', row)">Invoice</AppButton>
          </div>
        </div>
      </template>

      <template v-else>
        <EmptyState v-if="!queue?.invoices_today.length" icon="receipt" title="No invoices yet today" description="Invoices you raise today are listed here for reprinting." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.invoices_today" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.customer_name || row.customer }}</p>
              <p class="truncate text-[12px] text-muted">
                {{ row.name }} · {{ time(row.creation) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span>
                <StatusBadge v-if="row.outstanding_amount > 0" tone="warning" :dot="false" class="ml-1">Unpaid</StatusBadge>
              </p>
              <p v-if="row.payments?.length" class="truncate text-[12px] text-subtle">{{ row.payments.map((p) => p.mode_of_payment).join(' + ') }}</p>
            </div>
            <AppButton
              v-if="row.payments?.length"
              size="sm"
              variant="ghost"
              icon="wallet"
              tabindex="-1"
              :disabled="busy"
              :aria-label="`Change the payment mode of ${row.name}`"
              @click="$emit('change-mode', row)"
            >
              Mode
            </AppButton>
            <AppButton size="sm" variant="secondary" icon="printer" tabindex="-1" @click="$emit('print', row)">Print</AppButton>
          </div>
        </div>
      </template>
    </div>
  </AppCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { CounterQueue, CounterQueueInvoice, CounterQueueOrder } from '../../types';
import { money, shortDate, time } from '../../utils/format';
import { AppButton, AppCard, AppIcon, EmptyState, StatusBadge } from '../ui';

type TabKey = 'held' | 'to_invoice' | 'invoices_today';
const TABS: { key: TabKey; label: string }[] = [
  { key: 'held', label: 'Held' },
  { key: 'to_invoice', label: 'To invoice' },
  { key: 'invoices_today', label: 'Today' },
];

const props = defineProps<{ queue: CounterQueue | null; loading?: boolean; busy?: boolean; currency: string }>();
defineEmits<{
  (e: 'refresh'): void;
  (e: 'resume', order: CounterQueueOrder): void;
  (e: 'invoice', order: CounterQueueOrder): void;
  /** Load a submitted order back into the cart to change it before it is invoiced. */
  (e: 'edit', order: CounterQueueOrder): void;
  (e: 'print', invoice: CounterQueueInvoice): void;
  /** Correct the mode a payment against this invoice was recorded under. */
  (e: 'change-mode', invoice: CounterQueueInvoice): void;
}>();

const tab = ref<TabKey>('to_invoice');
const counts = computed<Record<TabKey, number>>(() => ({
  held: props.queue?.held.length || 0,
  to_invoice: props.queue?.to_invoice.length || 0,
  invoices_today: props.queue?.invoices_today.length || 0,
}));

// Same rule as sales.update_submitted_sales_order: nothing invoiced or delivered yet.
const editable = (row: CounterQueueOrder) => !row.per_billed && !row.per_delivered && row.status !== 'On Hold';

defineExpose({ show: (key: TabKey) => (tab.value = key) });
</script>
