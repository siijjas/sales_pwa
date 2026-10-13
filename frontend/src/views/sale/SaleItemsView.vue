<template>
  <WorkspacePage :back="{ name: 'sell-customer' }" title="Items" :subtitle="customer ? `For ${customer.customer_name}` : ''">
    <template #actions>
      <AppButton size="sm" variant="ghost" @click="router.push({ name: 'sell-customer' })">Change</AppButton>
    </template>
    <template #sticky>
      <div class="space-y-2.5">
        <StepHeader :steps="STEPS" :current="1" />
        <SearchBar v-model="search" placeholder="Search catalog…" />
      </div>
    </template>

    <div class="space-y-4 pb-28">
      <AppAlert v-if="sale.orderName" tone="info" :message="`Editing draft ${sale.orderName}`" />
      <AppAlert v-if="error" tone="danger" :message="error" />
      <SkeletonList v-if="loading" :rows="6" height="5rem" />
      <EmptyState v-else-if="!items.length" icon="package" title="No items found" description="Adjust your search to find products." />

      <AppCard v-else padding="none" class="divide-y divide-line">
        <div v-for="item in items" :key="item.item_code" class="flex items-center gap-3 px-4 py-3">
          <div class="min-w-0 flex-1">
            <p class="truncate text-[15px] font-semibold leading-tight text-foreground">{{ item.item_name }}</p>
            <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
              <span class="tnum font-bold text-foreground">
                <template v-if="itemPrice(item) !== null">{{ currency }} {{ money(itemPrice(item)) }}</template>
                <span v-else class="font-medium text-subtle">N/A</span>
              </span>
              <span class="text-subtle">·</span>
              <span class="truncate text-muted">{{ item.item_code }}</span>
              <button
                type="button"
                class="flex h-6 w-6 items-center justify-center rounded-full text-subtle transition hover:bg-card-muted hover:text-foreground"
                aria-label="View sales history"
                @click="openHistory(item)"
              >
                <AppIcon name="clock" :size="14" />
              </button>
            </div>
            <div v-if="hasQty(item)" class="mt-1.5">
              <StatusBadge v-if="item.actual_qty! <= 0" tone="danger" :dot="false">Out of stock</StatusBadge>
              <StatusBadge v-else-if="item.actual_qty! < 5" tone="warning" :dot="false">Only {{ qty(item.actual_qty) }} left</StatusBadge>
              <StatusBadge v-else tone="success" :dot="false">{{ qty(item.actual_qty) }} available</StatusBadge>
            </div>
          </div>

          <!-- In the sale already: the badge reopens the quantity sheet -->
          <button
            v-if="sale.qtyOf(item.item_code) > 0"
            type="button"
            class="focus-ring flex min-h-touch shrink-0 items-center gap-1.5 rounded-2xl bg-primary/10 px-3 text-sm font-bold text-primary transition active:scale-95"
            @click="openSheet(item)"
          >
            <span class="tnum">× {{ qty(sale.qtyOf(item.item_code)) }}</span>
            <AppIcon name="edit" :size="14" />
          </button>
          <AppButton v-else variant="secondary" size="sm" icon="plus" :disabled="!canAdd(item)" @click="openSheet(item)">Add</AppButton>
        </div>
      </AppCard>
    </div>

    <StickyBar>
      <AppButton size="lg" block :disabled="!sale.lines.length" trailing-icon="arrow-right" @click="router.push({ name: 'sell-review' })">
        {{ sale.lines.length ? `Review order · ${plural(sale.lines.length, 'item')} · ${currency} ${money(sale.subtotal)}` : 'Add items to continue' }}
      </AppButton>
    </StickyBar>

    <QtyInputSheet
      v-model="sheetOpen"
      :title="selectedItem?.item_name || ''"
      :subtitle="selectedItem ? `${selectedItem.item_code} · ${selectedItem.stock_uom}` : undefined"
      :price="selectedItem ? `${currency} ${money(itemPrice(selectedItem))}` : undefined"
      :max-qty="!allowWithoutStock && selectedItem?.actual_qty !== undefined && selectedItem?.actual_qty !== null ? selectedItem.actual_qty : undefined"
      :initial-qty="selectedItem ? sale.qtyOf(selectedItem.item_code) : 0"
      :step="selectedItem?.must_be_whole_number ? 1 : 0.5"
      :whole-number="Boolean(selectedItem?.must_be_whole_number)"
      :uom="selectedItem?.stock_uom"
      :confirm-label="selectedItem && sale.qtyOf(selectedItem.item_code) > 0 ? 'Update qty' : 'Add to order'"
      @confirm="onQtyConfirmed"
    />

    <BottomSheet v-model="historyOpen" :title="historyItem ? historyItem.item_name : 'Sales history'" :subtitle="`Previous rate for ${customer?.customer_name || 'this customer'}`">
      <SkeletonList v-if="historyLoading" :rows="4" height="3.5rem" />
      <EmptyState v-else-if="!historyRows.length" icon="clock" title="No previous sales" :description="`${customer?.customer_name || 'This customer'} hasn't been sold this item before.`" />
      <div v-else class="divide-y divide-line">
        <div v-for="row in historyRows" :key="row.sales_order" class="flex items-center justify-between gap-3 py-3">
          <div class="min-w-0">
            <p class="truncate font-semibold text-foreground">{{ row.sales_order }}</p>
            <p class="mt-0.5 text-xs text-muted">{{ shortDate(row.transaction_date) }}</p>
          </div>
          <div class="shrink-0 text-right">
            <p class="tnum text-sm font-bold text-foreground">{{ currency }} {{ money(row.rate) }}</p>
            <p class="tnum text-xs text-muted">qty {{ qty(row.qty) }}</p>
          </div>
        </div>
      </div>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import type { Item, ItemSalesHistoryRow } from '../../types';
import { useSessionStore } from '../../stores/session';
import { useSaleStore } from '../../stores/sale';
import { money, qty, plural, shortDate } from '../../utils/format';
import WorkspacePage from '../../components/WorkspacePage.vue';
import { AppCard, AppAlert, AppButton, AppIcon, BottomSheet, EmptyState, QtyInputSheet, SearchBar, SkeletonList, StatusBadge, StepHeader, StickyBar } from '../../components/ui';

const STEPS = ['Customer', 'Items', 'Review'];

const store = useSessionStore();
const sale = useSaleStore();
const router = useRouter();

const customer = computed(() => sale.customer);
const currency = computed(() => store.currencyDisplay);
// Sales Profile.hide_unavailable_items: only what the van actually holds is listed.
// Field Sales never sells from a warehouse, so it always sees the full catalog.
const hideUnavailable = computed(() => !store.isManager && !store.isFieldSales && Boolean(store.driverConfig?.hide_unavailable_items));
// Sales Profile override: out-of-stock items can still be ordered; create_sales_invoice()
// then bills them without moving stock and delivers only what the van holds. Field Sales
// staff never sell from a warehouse, so for them the qty shown is information only.
const allowWithoutStock = computed(() => store.canOrderWithoutStock);

const search = ref('');
const items = ref<Item[]>([]);
const loading = ref(true);
const error = ref('');

const sheetOpen = ref(false);
const selectedItem = ref<Item | null>(null);

const historyOpen = ref(false);
const historyItem = ref<Item | null>(null);
const historyRows = ref<ItemSalesHistoryRow[]>([]);
const historyLoading = ref(false);

const itemPrice = (item: Item) => item.price_list_rate ?? item.standard_rate ?? 0;
const hasQty = (item: Item) => item.actual_qty !== undefined && item.actual_qty !== null;
const canAdd = (item: Item) => allowWithoutStock.value || !hasQty(item) || item.actual_qty! > 0;

let timer = 0;
const loadItems = async () => {
  if (!customer.value) return;
  loading.value = true;
  error.value = '';
  try {
    items.value = await api.listItems(search.value, customer.value.name, { hideUnavailable: hideUnavailable.value });
  } catch (e: any) {
    error.value = e?.message || 'Failed to load items';
  } finally {
    loading.value = false;
  }
};
watch(search, () => {
  clearTimeout(timer);
  timer = window.setTimeout(loadItems, 300);
});

function openSheet(item: Item) {
  if (!canAdd(item) && sale.qtyOf(item.item_code) === 0) return;
  selectedItem.value = item;
  sheetOpen.value = true;
}
function onQtyConfirmed(value: number) {
  if (selectedItem.value) sale.setQty(selectedItem.value, value);
}

async function openHistory(item: Item) {
  historyItem.value = item;
  historyOpen.value = true;
  historyLoading.value = true;
  historyRows.value = [];
  try {
    historyRows.value = await api.getItemSalesHistory(item.item_code, customer.value?.name);
  } catch (_e) {
    historyRows.value = [];
  } finally {
    historyLoading.value = false;
  }
}

onMounted(() => {
  if (!customer.value) {
    router.replace({ name: 'sell-customer' });
    return;
  }
  loadItems();
});
</script>
