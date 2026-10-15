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
        <EmptyState v-if="!queue?.held.length" icon="save" title="Nothing on hold" description="F7 parks the purchase being keyed in as a draft Purchase Order." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.held" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.supplier_name || row.supplier }}</p>
              <p class="truncate text-[12px] text-muted">{{ row.name }} · {{ time(row.modified) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span></p>
            </div>
            <AppButton size="sm" variant="secondary" icon="edit" tabindex="-1" :disabled="busy" @click="$emit('resume', row)">Resume</AppButton>
          </div>
        </div>
      </template>

      <template v-else-if="tab === 'to_bill'">
        <EmptyState v-if="!queue?.to_bill.length" icon="file-text" title="Nothing to bill" description="Purchase Orders you submit without billing wait here until the goods and the supplier's bill arrive." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.to_bill" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.supplier_name || row.supplier }}</p>
              <p class="truncate text-[12px] text-muted">{{ row.name }} · {{ shortDate(row.transaction_date) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span></p>
            </div>
            <AppButton size="sm" icon="file-text" tabindex="-1" :disabled="busy" @click="$emit('bill', row)">Bill</AppButton>
          </div>
        </div>
      </template>

      <template v-else>
        <EmptyState v-if="!queue?.bills_today.length" icon="receipt" title="No bills yet today" description="Purchase Invoices you raise today are listed here." />
        <div v-else class="divide-y divide-line">
          <div v-for="row in queue.bills_today" :key="row.name" class="flex items-center gap-3 px-3 py-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13.5px] font-semibold text-foreground">{{ row.supplier_name || row.supplier }}</p>
              <p class="truncate text-[12px] text-muted">
                {{ row.name }} · {{ time(row.creation) }} · <span class="tnum">{{ currency }} {{ money(row.grand_total) }}</span>
                <StatusBadge v-if="row.outstanding_amount > 0" tone="warning" :dot="false" class="ml-1">Unpaid</StatusBadge>
                <StatusBadge v-else tone="success" :dot="false" class="ml-1">Paid</StatusBadge>
              </p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </AppCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { PurchaseQueue, PurchaseQueueOrder } from '../../types';
import { money, shortDate, time } from '../../utils/format';
import { AppButton, AppCard, AppIcon, EmptyState, StatusBadge } from '../ui';

type TabKey = 'held' | 'to_bill' | 'bills_today';
const TABS: { key: TabKey; label: string }[] = [
  { key: 'held', label: 'Held' },
  { key: 'to_bill', label: 'To bill' },
  { key: 'bills_today', label: 'Today' },
];

const props = defineProps<{ queue: PurchaseQueue | null; loading?: boolean; busy?: boolean; currency: string }>();
defineEmits<{
  (e: 'refresh'): void;
  (e: 'resume', order: PurchaseQueueOrder): void;
  (e: 'bill', order: PurchaseQueueOrder): void;
}>();

const tab = ref<TabKey>('to_bill');
const counts = computed<Record<TabKey, number>>(() => ({
  held: props.queue?.held.length || 0,
  to_bill: props.queue?.to_bill.length || 0,
  bills_today: props.queue?.bills_today.length || 0,
}));

defineExpose({ show: (key: TabKey) => (tab.value = key) });
</script>
