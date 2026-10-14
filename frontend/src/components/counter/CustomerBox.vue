<template>
  <div class="relative">
    <div class="flex items-center gap-2">
      <div class="relative min-w-0 flex-1">
        <AppIcon name="user" :size="18" class="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle" />
        <input
          ref="input"
          v-model="text"
          type="text"
          autocomplete="off"
          spellcheck="false"
          class="field-input !min-h-[2.875rem] pl-10 pr-10 text-[15px] font-semibold"
          :class="modelValue && !editing ? 'text-foreground' : ''"
          :placeholder="placeholder"
          :aria-expanded="open"
          role="combobox"
          aria-autocomplete="list"
          @focus="onFocus"
          @input="onInput"
          @keydown="onKeydown"
          @blur="onBlur"
        />
        <button
          v-if="modelValue"
          type="button"
          tabindex="-1"
          class="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-subtle transition hover:bg-card-muted hover:text-foreground"
          aria-label="Change customer"
          @mousedown.prevent
          @click="clear"
        >
          <AppIcon name="x" :size="16" />
        </button>
      </div>
      <AppButton v-if="canCreate" size="sm" variant="secondary" icon="plus" tabindex="-1" @click="openNew">New</AppButton>
    </div>

    <!-- Results -->
    <div
      v-if="open"
      class="absolute left-0 right-0 top-full z-30 mt-1.5 max-h-80 overflow-y-auto rounded-2xl bg-elevated p-1.5 shadow-raised ring-1 ring-line"
      role="listbox"
    >
      <p v-if="loading && !results.length" class="px-3 py-2 text-[13px] text-muted">Searching…</p>
      <p v-else-if="!results.length" class="px-3 py-2 text-[13px] text-muted">
        No customer matches “{{ text }}”.
        <button v-if="canCreate" type="button" class="font-semibold text-primary" @mousedown.prevent @click="openNew">Add them</button>
      </p>
      <button
        v-for="(row, idx) in results"
        :key="row.name"
        type="button"
        role="option"
        :aria-selected="idx === highlighted"
        class="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition"
        :class="idx === highlighted ? 'bg-primary-soft text-primary' : 'hover:bg-card-muted'"
        @mousedown.prevent
        @mouseenter="highlighted = idx"
        @click="pick(row)"
      >
        <Avatar :name="row.customer_name" size="sm" />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[14px] font-semibold">{{ row.customer_name }}</span>
          <span class="block truncate text-[12px] text-muted">{{ row.name }}<template v-if="row.mobile_no"> · {{ row.mobile_no }}</template></span>
        </span>
      </button>
    </div>

    <BottomSheet v-model="newOpen" title="New customer">
      <div class="space-y-4">
        <AppAlert v-if="newError" tone="danger" :message="newError" />
        <FormField label="Customer name" required>
          <BaseInput v-model="newName" placeholder="e.g. Al Amal Grocery" @keyup.enter="submitNew" />
        </FormField>
        <FormField label="Mobile">
          <BaseInput v-model="newMobile" type="tel" inputmode="tel" placeholder="Optional" @keyup.enter="submitNew" />
        </FormField>
        <AppButton size="lg" block :loading="creating" @click="submitNew">Add customer</AppButton>
      </div>
    </BottomSheet>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import * as api from '../../api/frappe';
import type { Customer } from '../../types';
import { AppAlert, AppButton, AppIcon, Avatar, BaseInput, BottomSheet, FormField } from '../ui';

const props = withDefaults(defineProps<{ modelValue: Customer | null; canCreate?: boolean; placeholder?: string }>(), {
  placeholder: 'Customer: type a name, ID or mobile',
});
const emit = defineEmits<{
  (e: 'update:modelValue', value: Customer | null): void;
  /** A customer was chosen (typed and confirmed, or created): the next field may take focus. */
  (e: 'picked', value: Customer): void;
}>();

const input = ref<HTMLInputElement | null>(null);
const text = ref('');
const editing = ref(false);
const results = ref<Customer[]>([]);
const highlighted = ref(0);
const loading = ref(false);
const open = computed(() => editing.value && (text.value.trim().length > 0 || results.value.length > 0));
let timer: number | undefined;
let requestSeq = 0;
let enterPending = false;

const label = (c: Customer | null) => (c ? (c.customer_name === c.name ? c.name : `${c.customer_name} · ${c.name}`) : '');

watch(
  () => props.modelValue,
  (c) => {
    if (!editing.value) text.value = label(c);
  },
  { immediate: true },
);

function onFocus() {
  editing.value = true;
  // Typing replaces the current customer; selecting the text makes that one keystroke.
  nextTick(() => input.value?.select());
  if (!text.value.trim() || props.modelValue) search(props.modelValue ? '' : text.value);
}

function onInput() {
  editing.value = true;
  search(text.value);
}

function search(q: string) {
  window.clearTimeout(timer);
  const seq = ++requestSeq;
  // Stale rows must not stay on screen: Enter would pick one of them.
  results.value = [];
  loading.value = true;
  timer = window.setTimeout(async () => {
    try {
      const rows = await api.searchCustomers(q, 12);
      if (seq !== requestSeq) return;
      results.value = rows;
      highlighted.value = 0;
      if (enterPending) {
        enterPending = false;
        if (rows[0]) pick(rows[0]);
      }
    } catch (_e) {
      if (seq === requestSeq) results.value = [];
    } finally {
      if (seq === requestSeq) loading.value = false;
    }
  }, 150);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' && results.value.length) {
    e.preventDefault();
    highlighted.value = (highlighted.value + 1) % results.value.length;
  } else if (e.key === 'ArrowUp' && results.value.length) {
    e.preventDefault();
    highlighted.value = (highlighted.value - 1 + results.value.length) % results.value.length;
  } else if (e.key === 'Enter') {
    // An empty box with no customer has nothing to do with Enter: let it reach the screen (a sheet that just opened).
    if (!results.value.length && !text.value.trim() && !props.modelValue && !loading.value) return;
    e.preventDefault();
    e.stopPropagation();
    const row = results.value[highlighted.value];
    if (row) pick(row);
    else if (loading.value && text.value.trim()) enterPending = true; // results still on their way
    else if (props.modelValue && !text.value.trim()) clear();
    else if (props.modelValue) {
      // Nothing new chosen: keep the current customer and move on.
      editing.value = false;
      text.value = label(props.modelValue);
      emit('picked', props.modelValue);
    }
  } else if (e.key === 'Escape' && editing.value) {
    e.stopPropagation();
    cancelEdit();
  } else if (e.key === 'Tab' && editing.value) {
    const row = results.value[highlighted.value];
    if (row && text.value.trim() && text.value !== label(props.modelValue)) pick(row, false);
    else cancelEdit();
  }
}

function cancelEdit() {
  editing.value = false;
  enterPending = false;
  results.value = [];
  text.value = label(props.modelValue);
  input.value?.blur();
}

function onBlur() {
  // Let a click on a result land first (results use mousedown.prevent, so this only fires for real blurs).
  window.setTimeout(() => {
    if (editing.value) cancelEdit();
  }, 0);
}

function pick(row: Customer, announce = true) {
  editing.value = false;
  enterPending = false;
  results.value = [];
  text.value = label(row);
  emit('update:modelValue', row);
  if (announce) emit('picked', row);
}

function clear() {
  emit('update:modelValue', null);
  text.value = '';
  results.value = [];
  editing.value = true;
  nextTick(() => input.value?.focus());
  search('');
}

// ─── New customer ───────────────────────────────────────────────────────
const newOpen = ref(false);
const newName = ref('');
const newMobile = ref('');
const newError = ref('');
const creating = ref(false);

function openNew() {
  newName.value = editing.value ? text.value.trim() : '';
  newMobile.value = '';
  newError.value = '';
  editing.value = false;
  results.value = [];
  newOpen.value = true;
}

async function submitNew() {
  if (!newName.value.trim() || creating.value) return;
  creating.value = true;
  newError.value = '';
  try {
    const created = await api.createCustomer(newName.value.trim(), newMobile.value.trim() || undefined);
    newOpen.value = false;
    pick(created);
  } catch (e: any) {
    newError.value = e?.message || 'Could not create the customer';
  } finally {
    creating.value = false;
  }
}

defineExpose({ focus: () => input.value?.focus() });
</script>
