<template>
  <div class="relative">
    <div class="grid items-center gap-2" :class="allowRate ? 'grid-cols-[minmax(0,1fr)_7rem_8rem_auto]' : 'grid-cols-[minmax(0,1fr)_7rem_auto]'">
      <!-- Item -->
      <div class="relative min-w-0">
        <AppIcon :name="picked ? 'check' : 'search'" :size="18" class="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2" :class="picked ? 'text-success' : 'text-subtle'" />
        <input
          ref="itemInput"
          v-model="text"
          type="text"
          autocomplete="off"
          spellcheck="false"
          role="combobox"
          aria-autocomplete="list"
          :aria-expanded="open"
          class="field-input !min-h-[2.875rem] pl-10 pr-3 text-[15px] font-semibold"
          :placeholder="placeholder"
          @input="onInput"
          @keydown="onItemKeydown"
          @focus="onFocus"
          @blur="onBlur"
        />
        <!-- What was picked: price and stock, so the cashier sees it before the line lands -->
        <div v-if="picked" class="pointer-events-none absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2 text-[12px]">
          <span class="tnum font-bold text-foreground">{{ currency }} {{ money(picked.price_list_rate) }}</span>
          <StatusBadge v-if="picked.actual_qty !== null && picked.is_stock_item" :tone="stockTone(picked.actual_qty)" :dot="false">{{ fmtQty(picked.actual_qty) }} {{ picked.stock_uom }}</StatusBadge>
        </div>
      </div>

      <!-- Qty -->
      <input
        ref="qtyInput"
        v-model="qtyText"
        type="text"
        inputmode="decimal"
        autocomplete="off"
        class="field-input tnum !min-h-[2.875rem] px-3 text-right text-[15px] font-bold"
        placeholder="Qty"
        :disabled="!picked"
        @keydown="onQtyKeydown"
        @focus="($event.target as HTMLInputElement).select()"
      />

      <!-- Rate (profile permitting) -->
      <input
        v-if="allowRate"
        ref="rateInput"
        v-model="rateText"
        type="text"
        inputmode="decimal"
        autocomplete="off"
        class="field-input tnum !min-h-[2.875rem] px-3 text-right text-[15px] font-semibold"
        placeholder="Rate"
        :disabled="!picked"
        @keydown="onRateKeydown"
        @focus="($event.target as HTMLInputElement).select()"
      />

      <AppButton size="sm" icon="plus" :disabled="!picked || !(qty > 0)" tabindex="-1" @click="commit">Add</AppButton>
    </div>

    <!-- Results -->
    <div
      v-if="open"
      class="absolute left-0 z-30 mt-1.5 max-h-96 w-full max-w-2xl overflow-y-auto rounded-2xl bg-elevated p-1.5 shadow-raised ring-1 ring-line"
      role="listbox"
    >
      <p v-if="loading && !results.length" class="px-3 py-2 text-[13px] text-muted">Searching…</p>
      <p v-else-if="!results.length" class="px-3 py-2 text-[13px] text-muted">No item matches “{{ text }}”.</p>
      <button
        v-for="(row, idx) in results"
        :key="row.item_code"
        type="button"
        role="option"
        :aria-selected="idx === highlighted"
        class="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition"
        :class="idx === highlighted ? 'bg-primary-soft text-primary' : 'hover:bg-card-muted'"
        @mousedown.prevent
        @mouseenter="highlighted = idx"
        @click="pick(row)"
      >
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[14px] font-semibold">{{ row.item_name }}</span>
          <span class="block truncate text-[12px]" :class="idx === highlighted ? 'text-primary/80' : 'text-muted'">{{ row.item_code }} · {{ row.stock_uom }}</span>
        </span>
        <span class="tnum shrink-0 text-[13px] font-bold">{{ currency }} {{ money(row.price_list_rate) }}</span>
        <span v-if="row.actual_qty !== null && row.is_stock_item" class="w-20 shrink-0 text-right">
          <StatusBadge :tone="stockTone(row.actual_qty)" :dot="false">{{ fmtQty(row.actual_qty) }}</StatusBadge>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import * as api from '../../api/frappe';
import type { CounterItem } from '../../types';
import { money, qty as qtyFmt } from '../../utils/format';
import { AppButton, AppIcon, StatusBadge } from '../ui';

const props = withDefaults(
  defineProps<{
    customer: string | null;
    currency: string;
    allowRate?: boolean;
    /** Profile: out-of-stock items can still be keyed in (the invoice then delivers what there is). */
    allowWithoutStock?: boolean;
    placeholder?: string;
  }>(),
  { placeholder: 'Item: type a code, name or barcode' },
);
const emit = defineEmits<{
  (e: 'add', item: CounterItem, qty: number, rate: number): void;
  /** Arrow-down out of an empty item box: the caller may move focus into the lines below. */
  (e: 'down'): void;
}>();

const itemInput = ref<HTMLInputElement | null>(null);
const qtyInput = ref<HTMLInputElement | null>(null);
const rateInput = ref<HTMLInputElement | null>(null);

const text = ref('');
const picked = ref<CounterItem | null>(null);
const results = ref<CounterItem[]>([]);
const highlighted = ref(0);
const loading = ref(false);
const listOpen = ref(false);
const open = computed(() => listOpen.value && !picked.value && text.value.trim().length > 0);
const qtyText = ref('1');
const rateText = ref('');
const qty = computed(() => Number(String(qtyText.value).replace(/[^0-9.]/g, '')) || 0);
const rate = computed(() => Number(String(rateText.value).replace(/[^0-9.]/g, '')) || 0);

let timer: number | undefined;
let requestSeq = 0;
let controller: AbortController | null = null;
let pending: Promise<void> | null = null;
let enterPending = false;

const fmtQty = (n: number) => qtyFmt(n);
const stockTone = (n: number) => (n <= 0 ? 'danger' : n < 5 ? 'warning' : 'success');

function onFocus() {
  if (picked.value) nextTick(() => itemInput.value?.select());
  listOpen.value = true;
}

function onInput() {
  // Typing again after a pick starts a new search.
  picked.value = null;
  listOpen.value = true;
  search(text.value);
}

function search(q: string) {
  window.clearTimeout(timer);
  controller?.abort();
  const seq = ++requestSeq;
  const query = q.trim();
  if (!query) {
    results.value = [];
    loading.value = false;
    pending = null;
    return;
  }
  // Stale rows must not stay on screen: an arrow key would walk them.
  results.value = [];
  loading.value = true;
  pending = new Promise<void>((resolve) => {
    timer = window.setTimeout(async () => {
      controller = new AbortController();
      try {
        const res = await api.searchCounterItems(query, props.customer, 15, controller.signal);
        if (seq !== requestSeq) return;
        results.value = res.items;
        highlighted.value = 0;
        if (enterPending) {
          enterPending = false;
          const row = res.items.find((i) => i.exact) || res.items[0];
          if (row) pick(row);
        }
      } catch (_e) {
        if (seq === requestSeq) results.value = [];
      } finally {
        if (seq === requestSeq) loading.value = false;
        resolve();
      }
    }, 120);
  });
}

function onItemKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    if (results.value.length && !picked.value && text.value.trim()) {
      e.preventDefault();
      highlighted.value = (highlighted.value + 1) % results.value.length;
    } else if (!text.value.trim()) {
      e.preventDefault();
      emit('down');
    }
  } else if (e.key === 'ArrowUp' && results.value.length && !picked.value && text.value.trim()) {
    e.preventDefault();
    highlighted.value = (highlighted.value - 1 + results.value.length) % results.value.length;
  } else if (e.key === 'Enter') {
    e.preventDefault();
    e.stopPropagation();
    if (picked.value) {
      focusQty();
      return;
    }
    if (!text.value.trim()) return;
    if (loading.value) {
      // Results still on their way (a fast typist on a slow link): act on them when they land.
      enterPending = true;
      return;
    }
    const row = results.value.find((i) => i.exact) || results.value[highlighted.value];
    if (row) pick(row);
  } else if (e.key === 'Tab' && !e.shiftKey && !picked.value && text.value.trim()) {
    const row = results.value.find((i) => i.exact) || results.value[highlighted.value];
    if (row) pick(row, false);
  } else if (e.key === 'Escape') {
    if (text.value || picked.value) {
      e.stopPropagation();
      resetEntry();
    }
  }
}

function onBlur() {
  window.setTimeout(() => {
    listOpen.value = false;
  }, 0);
}

function pick(row: CounterItem, moveFocus = true) {
  picked.value = row;
  results.value = [];
  listOpen.value = false;
  enterPending = false;
  text.value = `${row.item_code} · ${row.item_name}`;
  rateText.value = String(row.price_list_rate ?? 0);
  if (!(qty.value > 0)) qtyText.value = '1';
  if (moveFocus) focusQty();
}

function focusQty() {
  nextTick(() => {
    qtyInput.value?.focus();
    qtyInput.value?.select();
  });
}

function onQtyKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault();
    e.stopPropagation();
    commit();
  } else if (e.key === 'Escape') {
    e.stopPropagation();
    resetEntry();
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    // Nudge: whole-number items step by one, others by 0.5.
    e.preventDefault();
    const step = picked.value?.must_be_whole_number ? 1 : 0.5;
    const next = Math.max(0, qty.value + (e.key === 'ArrowUp' ? step : -step));
    qtyText.value = String(next);
  }
}

function onRateKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault();
    e.stopPropagation();
    commit();
  } else if (e.key === 'Escape') {
    e.stopPropagation();
    resetEntry();
  }
}

function commit() {
  const item = picked.value;
  if (!item || !(qty.value > 0)) return;
  const finalQty = item.must_be_whole_number ? Math.round(qty.value) : qty.value;
  if (finalQty <= 0) return;
  emit('add', item, finalQty, props.allowRate ? rate.value : item.price_list_rate);
  resetEntry();
}

function resetEntry() {
  picked.value = null;
  text.value = '';
  results.value = [];
  qtyText.value = '1';
  rateText.value = '';
  enterPending = false;
  nextTick(() => itemInput.value?.focus());
}

defineExpose({
  focus: () => itemInput.value?.focus(),
  reset: resetEntry,
  /** Whether a search list is showing (the parent leaves Escape to the row then). */
  isOpen: () => open.value,
  pendingSearch: () => pending,
});
</script>
