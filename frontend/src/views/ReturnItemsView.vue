<template>
  <WorkspacePage back title="Return items" :subtitle="customer ? `From ${customer.customer_name}` : undefined">
    <template #sticky>
      <SearchBar v-model="search" placeholder="Search items…" />
    </template>

    <div class="space-y-3 pb-28">
      <AppAlert v-if="error" tone="danger" :message="error" />
      <SkeletonList v-if="loading && !items.length" :rows="6" height="4.5rem" />
      <EmptyState v-else-if="!items.length" icon="package" title="No items found" description="Adjust your search." />
      <AppCard v-else padding="none" class="divide-y divide-line" :class="loading ? 'opacity-60' : ''">
        <ListRow v-for="item in items" :key="item.item_code" :title="item.item_name" :subtitle="`${item.item_code} · ${item.stock_uom}`">
          <template #subtitle>
            <span class="tnum font-semibold text-foreground">{{ currency }} {{ money(itemPrice(item)) }}</span>
            <span class="text-subtle"> · {{ item.item_code }}</span>
          </template>
          <template #trailing>
            <button
              v-if="returns.qtyOf(item.item_code) > 0"
              type="button"
              class="focus-ring flex items-center gap-1.5 rounded-2xl bg-danger/12 px-3 py-2 text-sm font-bold text-danger transition active:scale-95"
              @click="openSheet(item)"
            >
              <span class="tnum">× {{ qty(returns.qtyOf(item.item_code)) }}</span>
              <AppIcon name="edit" :size="14" />
            </button>
            <AppButton v-else variant="secondary" size="sm" icon="plus" @click="openSheet(item)">Add</AppButton>
          </template>
        </ListRow>
      </AppCard>
    </div>

    <StickyBar v-if="returns.lines.length">
      <button
        type="button"
        class="focus-ring flex w-full items-center justify-between gap-3 rounded-2xl bg-danger px-4 py-2 text-danger-fg"
        @click="router.push({ name: 'return-review', params: { name } })"
      >
        <span class="flex items-center gap-3">
          <span class="tnum flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 text-sm font-bold">{{ returns.lines.length }}</span>
          <span class="text-left">
            <span class="block text-[11px] font-semibold uppercase tracking-wide opacity-80">Return total</span>
            <span class="tnum block text-lg font-bold leading-tight">{{ currency }} {{ money(returns.total) }}</span>
          </span>
        </span>
        <span class="flex items-center gap-1 text-base font-bold">Review <AppIcon name="arrow-right" :size="18" /></span>
      </button>
    </StickyBar>

    <QtyInputSheet
      v-model="sheetOpen"
      :title="selected?.item_name || ''"
      :subtitle="selected ? `${selected.item_code} · ${selected.stock_uom}` : undefined"
      :price="selected ? `${currency} ${money(itemPrice(selected))}` : undefined"
      :initial-qty="selected ? returns.qtyOf(selected.item_code) : 0"
      :step="selected?.must_be_whole_number ? 1 : 0.5"
      :whole-number="Boolean(selected?.must_be_whole_number)"
      :uom="selected?.stock_uom"
      :confirm-label="selected && returns.qtyOf(selected.item_code) > 0 ? 'Update qty' : 'Add to return'"
      @confirm="onQtyConfirmed"
    />
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { Customer, Item } from '../types';
import { useSessionStore } from '../stores/session';
import { useReturnStore } from '../stores/returns';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { money, qty } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, ListRow, SearchBar, SkeletonList, EmptyState, StickyBar, QtyInputSheet } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const returns = useReturnStore();
const shift = useShiftStore();
const toast = useToast();

const name = computed(() => String(route.params.name));
const currency = computed(() => store.currencyDisplay);
const customer = ref<Customer | null>(null);
const search = ref('');
const items = ref<Item[]>([]);
const loading = ref(true);
const error = ref('');

const sheetOpen = ref(false);
const selected = ref<Item | null>(null);

const itemPrice = (item: Item) => item.price_list_rate ?? item.standard_rate ?? 0;

let timer = 0;
let seq = 0;
const loadItems = async () => {
  const mine = ++seq;
  loading.value = true;
  error.value = '';
  try {
    const rows = await api.listItems(search.value, name.value);
    if (mine === seq) items.value = rows;
  } catch (e: any) {
    if (mine === seq) error.value = e?.message || 'Failed to load items';
  } finally {
    if (mine === seq) loading.value = false;
  }
};

onMounted(async () => {
  await shift.refresh();
  if (shift.needsShift) {
    toast.warning(shift.isStale ? 'Close your previous shift first' : 'Open your shift first', { message: 'Returns need an open shift.' });
    router.replace(shift.gateRoute);
    return;
  }
  try {
    customer.value = await api.getCustomer(name.value);
    returns.start(customer.value);
  } catch (e: any) {
    error.value = e?.message || 'Customer not found';
    loading.value = false;
    return;
  }
  loadItems();
});

watch(search, () => {
  window.clearTimeout(timer);
  timer = window.setTimeout(loadItems, 300);
});

function openSheet(item: Item) {
  selected.value = item;
  sheetOpen.value = true;
}
function onQtyConfirmed(value: number) {
  if (selected.value) returns.setQty(selected.value, value);
}
</script>
