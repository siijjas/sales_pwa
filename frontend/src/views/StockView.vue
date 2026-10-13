<template>
  <WorkspacePage :title="dashboard?.warehouse || sellingWarehouse || 'Stock'" subtitle="Live stock">
    <template #actions>
      <AppButton variant="ghost" size="sm" icon="refresh" :loading="loading" @click="refresh(true)" />
      <AppButton v-if="canLoad" size="sm" icon="truck" @click="router.push({ name: 'stock-load' })">Load van</AppButton>
    </template>
    <template #sticky>
      <SearchBar v-model="search" placeholder="Filter by item name or code…" />
    </template>

    <div class="space-y-4">
      <AppAlert v-if="offlineSnapshot" tone="warning" :message="`Showing the snapshot from ${dateTime(dashboard?.generated_at)} — live data is unavailable.`" />
      <AppAlert v-if="error" tone="danger" :message="error" />
      <AppAlert v-if="!driverConfig && !store.isManager" tone="info" message="No active sales profile is assigned. Ask a manager to assign one before opening stock." />

      <div v-if="dashboard" class="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <KpiTile label="Items" :value="dashboard.summary.item_count" icon="package" tone="primary" />
        <KpiTile label="Low stock" :value="dashboard.summary.low_stock_count" :sub="`At or below ${qty(dashboard.low_stock_threshold)}`" icon="alert" :tone="dashboard.summary.low_stock_count ? 'warning' : 'info'" />
        <KpiTile label="Available" :value="qty(dashboard.summary.total_available_qty)" icon="boxes" tone="success" />
        <KpiTile label="Reserved" :value="qty(dashboard.summary.total_reserved_qty)" icon="clock" tone="info" />
      </div>

      <p v-if="dashboard?.source_warehouse" class="px-0.5 text-[12px] text-muted">Loaded from <span class="font-semibold text-foreground">{{ dashboard.source_warehouse }}</span></p>

      <SkeletonList v-if="loading && !dashboard" :rows="5" height="4rem" />
      <EmptyState v-else-if="dashboard && !filteredItems.length" icon="boxes" :title="search ? 'No matches' : 'Nothing in stock'" :description="search ? 'No stock matches the current filter.' : 'Load the van to see items here.'" />

      <AppCard v-else-if="dashboard" padding="none" class="divide-y divide-line">
        <ListRow v-for="item in filteredItems" :key="item.item_code" :title="item.item_name" :subtitle="`${item.item_code} · ${item.stock_uom}`">
          <template #leading>
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="item.is_low_stock ? 'bg-warning/16 text-warning' : 'bg-card-muted text-muted'">
              <AppIcon :name="item.is_low_stock ? 'alert' : 'package'" :size="18" />
            </span>
          </template>
          <template #trailing>
            <div class="text-right">
              <p class="tnum text-[16px] font-bold leading-tight" :class="item.is_low_stock ? 'text-warning' : 'text-foreground'">{{ qty(item.actual_qty) }}</p>
              <p class="tnum text-[11px] text-muted">
                <template v-if="item.reserved_qty">{{ qty(item.reserved_qty) }} reserved</template>
                <template v-else-if="item.projected_qty !== item.actual_qty">{{ qty(item.projected_qty) }} projected</template>
                <template v-else>available</template>
              </p>
            </div>
          </template>
        </ListRow>
      </AppCard>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { DriverStockDashboard } from '../types';
import { useSessionStore } from '../stores/session';
import { qty, dateTime } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, KpiTile, ListRow, SearchBar, SkeletonList, EmptyState } from '../components/ui';

const CACHE_KEY = 'sales-app-stock-cache';

const store = useSessionStore();
const router = useRouter();
const driverConfig = computed(() => store.driverConfig);
// The van warehouse, or the main warehouse for a van that sells straight from it.
const sellingWarehouse = computed(
  () => driverConfig.value?.selling_warehouse || driverConfig.value?.van_warehouse || driverConfig.value?.source_warehouse || null,
);
const canLoad = computed(() => (driverConfig.value ? store.capabilities.can_load_stock : store.isManager));
const dashboard = ref<DriverStockDashboard | null>(null);
const loading = ref(true);
const error = ref('');
const offlineSnapshot = ref(false);
const search = ref('');

const filteredItems = computed(() => {
  const text = search.value.trim().toLowerCase();
  const items = dashboard.value?.items || [];
  if (!text) return items;
  return items.filter((item) => [item.item_code, item.item_name].some((value) => value.toLowerCase().includes(text)));
});

function readCachedSnapshot() {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    return cached ? (JSON.parse(cached) as DriverStockDashboard) : null;
  } catch (_error) {
    return null;
  }
}

async function refresh(forceRefresh = false) {
  if (!sellingWarehouse.value && !store.isManager) {
    dashboard.value = null;
    error.value = 'No active sales profile is assigned to this user.';
    offlineSnapshot.value = false;
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = '';
  offlineSnapshot.value = false;
  try {
    const data = await api.getDriverStockDashboard(forceRefresh);
    dashboard.value = data;
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    } catch (_e) {
      /* storage unavailable: fine */
    }
  } catch (err: any) {
    const cached = readCachedSnapshot();
    if (cached) {
      dashboard.value = cached;
      offlineSnapshot.value = true;
    } else {
      error.value = err?.message || 'Failed to load stock';
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => refresh(false));
</script>
