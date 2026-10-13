<template>
  <WorkspacePage back title="Shift reports" subtitle="Closing reports for every closed shift">
    <SkeletonList v-if="loading" :rows="4" height="5rem" />

    <div v-else class="space-y-5">
      <AppCard v-if="activeShift" padding="none">
        <ListRow interactive chevron icon="activity" tone="success" title="Shift summary" :subtitle="`Open shift${activeShift.period_start ? `, since ${time(activeShift.period_start)}` : ''}`" @click="router.push({ name: 'shift-summary' })" />
      </AppCard>

      <section>
        <SectionHeader title="Closed shifts" />
        <AppAlert v-if="error" tone="danger" :message="error" />
        <EmptyState v-else-if="!closings.length" icon="receipt" title="No closed shifts yet" description="Closing reports appear here once a shift is closed." />
        <AppCard v-else padding="none" class="divide-y divide-line">
          <ListRow
            v-for="c in closings"
            :key="c.name"
            interactive
            chevron
            :title="store.isManager ? `${c.driver_name || c.driver} · ${shortDate(c.shift_date)}` : longDate(c.shift_date)"
            :subtitle="`${time(c.period_start) || '—'} – ${time(c.period_end) || '—'}${c.closed_by ? ' · closed by manager' : ''}${c.draft_orders_count ? ` · ${plural(c.draft_orders_count, 'draft')} left` : ''}`"
            @click="router.push({ name: 'closing-report', params: { name: c.name } })"
          >
            <template #trailing>
              <div class="text-right">
                <p class="tnum text-sm font-bold text-foreground">{{ currency }} {{ money(c.total_sales) }}</p>
                <p v-if="c.net_difference" class="tnum text-xs font-semibold" :class="c.variance_status === 'Within Tolerance' ? 'text-warning' : c.net_difference > 0 ? 'text-success' : 'text-danger'">
                  {{ signedMoney(c.net_difference) }} {{ c.variance_status === 'Within Tolerance' ? 'within tolerance' : 'variance' }}
                </p>
                <p v-else class="text-xs text-muted">Balanced</p>
              </div>
            </template>
          </ListRow>
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import { money, signedMoney, plural, shortDate, longDate, time } from '../utils/format';
import type { ActiveShift, ShiftClosingListRow } from '../types';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppAlert, EmptyState, ListRow, SectionHeader, SkeletonList } from '../components/ui';

const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);

const loading = ref(true);
const error = ref('');
const activeShift = ref<ActiveShift | null>(null);
const closings = ref<ShiftClosingListRow[]>([]);

onMounted(async () => {
  try {
    const [shift, rows] = await Promise.all([
      store.capabilities.uses_shifts && store.driverConfig ? api.getActiveShift().catch(() => null) : Promise.resolve(null),
      api.getShiftClosings(),
    ]);
    activeShift.value = shift;
    closings.value = rows;
  } catch (e: any) {
    error.value = e?.message || 'Could not load shift reports.';
  } finally {
    loading.value = false;
  }
});
</script>
