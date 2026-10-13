<template>
  <WorkspacePage :back="{ name: 'stock' }" title="Load van" subtitle="Transfer stock from the main warehouse">
    <div class="space-y-4 pb-32">
      <!-- Route -->
      <AppCard padding="sm">
        <div class="flex items-center gap-2">
          <div class="min-w-0 flex-1 rounded-2xl bg-card-muted px-3 py-2.5">
            <p class="text-[11px] font-semibold uppercase tracking-wide text-muted">From</p>
            <p class="truncate text-sm font-bold text-foreground">{{ driverConfig?.source_warehouse || 'Not configured' }}</p>
          </div>
          <AppIcon name="arrow-right" :size="20" class="shrink-0 text-subtle" />
          <div class="min-w-0 flex-1 rounded-2xl bg-primary-soft px-3 py-2.5">
            <p class="text-[11px] font-semibold uppercase tracking-wide text-primary">To</p>
            <p class="truncate text-sm font-bold text-foreground">{{ driverConfig?.van_warehouse || 'Not configured' }}</p>
          </div>
        </div>
      </AppCard>

      <AppAlert v-if="error" tone="danger" :message="error" />

      <!-- Lines -->
      <section>
        <SectionHeader title="This load" :description="lines.length ? plural(lines.length, 'line') : 'Nothing added yet'" />
        <EmptyState v-if="!lines.length" icon="truck" title="No lines yet" description="Search the main warehouse below and add what you are loading." />
        <div v-else class="space-y-2.5">
          <AppCard v-for="line in lines" :key="line.item_code" class="space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate font-semibold text-foreground">{{ line.item_name }}</p>
                <p class="text-xs text-muted">{{ line.item_code }} · {{ line.stock_uom }} · {{ qty(line.available_qty) }} available</p>
              </div>
              <button type="button" class="shrink-0 text-sm font-semibold text-danger" @click="removeLine(line.item_code)">Remove</button>
            </div>
            <FormField label="Quantity" :error="line.qty > line.available_qty ? 'More than the main warehouse holds.' : undefined">
              <BaseInput :model-value="line.qty" type="number" inputmode="decimal" min="0" @update:modelValue="(v) => setQty(line.item_code, v)" />
            </FormField>
            <FormField v-if="line.has_batch_no" label="Batch" required>
              <BaseSelect :model-value="line.batch_no || ''" placeholder="Select batch" @update:modelValue="(v) => setBatch(line.item_code, v)">
                <option v-for="batch in detailMap[line.item_code]?.batches || []" :key="batch.batch_no" :value="batch.batch_no">
                  {{ batch.batch_no }} · {{ qty(batch.available_qty) }}
                </option>
              </BaseSelect>
            </FormField>
            <FormField v-if="line.has_serial_no" label="Serial numbers" :hint="`Entered ${(line.serial_nos || []).length} of ${Math.trunc(line.qty)}`">
              <BaseTextarea :model-value="(line.serial_nos || []).join('\n')" :rows="4" placeholder="One serial number per line" @update:modelValue="(v) => setSerials(line.item_code, v)" />
            </FormField>
          </AppCard>
        </div>
      </section>

      <!-- Source search -->
      <section>
        <SectionHeader title="Add from main warehouse" />
        <AppCard padding="sm" class="space-y-3">
          <SearchBar v-model="search" placeholder="Search by item name or code…" />
          <SkeletonList v-if="searchLoading" :rows="2" height="3.5rem" />
          <div v-else class="max-h-96 divide-y divide-line overflow-y-auto">
            <ListRow v-for="item in searchResults" :key="item.item_code" dense :title="item.item_name" :subtitle="`${item.item_code} · ${qty(item.actual_qty)} ${item.stock_uom}`">
              <template #trailing>
                <div class="flex items-center gap-1.5">
                  <StatusBadge v-if="item.has_batch_no" tone="info" :dot="false">Batch</StatusBadge>
                  <StatusBadge v-if="item.has_serial_no" tone="info" :dot="false">Serial</StatusBadge>
                  <AppButton variant="secondary" size="sm" icon="plus" :disabled="lines.some((l) => l.item_code === item.item_code)" @click="openAddSheet(item)">
                    {{ lines.some((l) => l.item_code === item.item_code) ? 'Added' : 'Add' }}
                  </AppButton>
                </div>
              </template>
            </ListRow>
            <p v-if="!searchResults.length" class="py-3 text-center text-sm text-muted">No stock in the main warehouse matches this search.</p>
          </div>
        </AppCard>
      </section>

      <AppCard padding="lg">
        <FormField label="Note" hint="Optional, saved on the Stock Entry.">
          <BaseTextarea v-model="remarks" :rows="2" placeholder="e.g. Morning load, route North" />
        </FormField>
      </AppCard>
    </div>

    <StickyBar>
      <AppButton size="lg" block icon="truck" :disabled="!canSubmit" :loading="submitting" @click="submitTransfer">
        {{ submitting ? 'Submitting…' : lines.length ? `Submit transfer · ${plural(lines.length, 'line')}` : 'Add lines to transfer' }}
      </AppButton>
    </StickyBar>

    <QtyInputSheet
      v-model="addSheetOpen"
      :title="pendingDetail?.item_name || ''"
      :subtitle="pendingDetail ? `${pendingDetail.item_code} · ${pendingDetail.stock_uom}` : undefined"
      :max-qty="pendingDetail?.source_qty"
      :uom="pendingDetail?.stock_uom"
      confirm-label="Add to load"
      @confirm="onTransferQtyConfirmed"
    />
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { Item, StockTransferLine, TransferItemDetail } from '../types';
import { useSessionStore } from '../stores/session';
import { useToast } from '../composables/useToast';
import { qty, plural } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, FormField, BaseInput, BaseSelect, BaseTextarea, ListRow, SearchBar, SectionHeader, StatusBadge, SkeletonList, EmptyState, StickyBar, QtyInputSheet } from '../components/ui';

const store = useSessionStore();
const router = useRouter();
const toast = useToast();
const driverConfig = computed(() => store.driverConfig);
const search = ref('');
const searchResults = ref<Item[]>([]);
const searchLoading = ref(false);
const lines = ref<StockTransferLine[]>([]);
const detailMap = ref<Record<string, TransferItemDetail>>({});
const submitting = ref(false);
const error = ref('');
const remarks = ref('');
const addSheetOpen = ref(false);
const pendingDetail = ref<TransferItemDetail | null>(null);

let searchTimer = window.setTimeout(() => undefined, 0);

const canSubmit = computed(() => {
  if (!lines.value.length) return false;
  return lines.value.every((line) => {
    if (!(line.qty > 0) || line.qty > line.available_qty) return false;
    if (line.has_batch_no && !line.batch_no) return false;
    if (line.has_serial_no && (line.serial_nos || []).length !== Math.trunc(line.qty)) return false;
    return true;
  });
});

async function loadItems() {
  if (!driverConfig.value?.source_warehouse || !driverConfig.value?.van_warehouse) {
    searchResults.value = [];
    error.value = 'This profile has no separate van warehouse, so there is nothing to load. Ask a manager to check the Sales Profile.';
    searchLoading.value = false;
    return;
  }
  searchLoading.value = true;
  error.value = '';
  try {
    searchResults.value = await api.searchTransferItems(search.value);
  } catch (err: any) {
    error.value = err?.message || 'Failed to load transfer items';
  } finally {
    searchLoading.value = false;
  }
}

async function openAddSheet(item: Item) {
  error.value = '';
  if (lines.value.some((line) => line.item_code === item.item_code)) return;
  try {
    const detail = await api.getTransferItemDetail(item.item_code);
    pendingDetail.value = detail;
    addSheetOpen.value = true;
  } catch (err: any) {
    error.value = err?.message || 'Failed to load item detail';
  }
}

function onTransferQtyConfirmed(q: number) {
  const detail = pendingDetail.value;
  if (!detail || q <= 0) return;
  detailMap.value = { ...detailMap.value, [detail.item_code]: detail };
  lines.value = [
    ...lines.value,
    {
      item_code: detail.item_code,
      item_name: detail.item_name,
      stock_uom: detail.stock_uom,
      qty: q,
      available_qty: detail.source_qty,
      has_batch_no: detail.has_batch_no,
      has_serial_no: detail.has_serial_no,
      batch_no: detail.batches[0]?.batch_no,
      serial_nos: [],
    },
  ];
  pendingDetail.value = null;
}

function removeLine(itemCode: string) {
  lines.value = lines.value.filter((line) => line.item_code !== itemCode);
}
function setQty(itemCode: string, value: string | number) {
  const nextQty = Number(value || 0);
  lines.value = lines.value.map((line) => (line.item_code === itemCode ? { ...line, qty: nextQty } : line));
}
function setBatch(itemCode: string, value: string) {
  lines.value = lines.value.map((line) => (line.item_code === itemCode ? { ...line, batch_no: value || undefined } : line));
}
function setSerials(itemCode: string, value: string) {
  const serials = value.split('\n').map((row) => row.trim()).filter(Boolean);
  lines.value = lines.value.map((line) => (line.item_code === itemCode ? { ...line, serial_nos: serials } : line));
}

async function submitTransfer() {
  if (!canSubmit.value) return;
  submitting.value = true;
  error.value = '';
  try {
    const result = await api.createStockTransfer(lines.value, remarks.value);
    toast.success('Van loaded', { message: `Stock Entry ${result.name} submitted to ${result.to_warehouse}.` });
    router.replace({ name: 'stock' });
  } catch (err: any) {
    error.value = err?.message || 'Failed to create stock transfer';
  } finally {
    submitting.value = false;
  }
}

watch(search, () => {
  clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadItems, 250);
});
onMounted(loadItems);
</script>
