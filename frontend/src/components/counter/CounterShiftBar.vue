<template>
  <div v-if="visible" class="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-2xl px-3 py-1.5 ring-1 ring-inset" :class="toneClass">
    <span class="flex min-w-0 items-center gap-2 text-[13px]">
      <AppIcon name="clock" :size="16" class="shrink-0" />
      <template v-if="shift.isStale">
        <span class="font-bold">Shift from {{ shortDate(shift.active!.shift_date) }} is still open</span>
        <span class="hidden text-[12.5px] opacity-80 sm:inline">Close it before today's work counts on a shift.</span>
      </template>
      <template v-else-if="shift.isOpen">
        <span class="font-bold">Shift open</span>
        <span class="tnum text-[12.5px] opacity-80">since {{ time(shift.active!.period_start) }}</span>
        <template v-if="drawer !== null">
          <span class="text-subtle">·</span>
          <span class="text-[12.5px] opacity-80">{{ drawerMode }}</span>
          <span class="tnum font-bold" title="Expected in the drawer: opening float + cash taken + handed over by linked staff − expenses − deposits − paid to suppliers">{{ currency }} {{ money(drawer) }}</span>
        </template>
        <template v-if="linkedOut.length">
          <span class="text-subtle">·</span>
          <span class="text-[12.5px] text-warning" :title="`Still on shift: ${linkedOut.join(', ')}. Their cash is handed over when they close.`">{{ linkedOut.length }} linked still on shift</span>
        </template>
      </template>
      <template v-else>
        <span class="font-bold">No shift open</span>
        <span class="hidden text-[12.5px] opacity-80 sm:inline">{{ shift.needsShift ? 'Your profile needs an open shift to sell.' : 'Open one so the drawer can be reconciled at closing.' }}</span>
      </template>
    </span>
    <span class="ml-auto flex flex-wrap items-center gap-1.5">
      <template v-if="shift.isOpen">
        <AppButton v-if="canExpense" size="sm" variant="ghost" icon="file-text" tabindex="-1" @click="emit('expense')">Expense <kbd class="ml-1 text-[11px] opacity-70">F6</kbd></AppButton>
        <AppButton size="sm" variant="ghost" icon="list" tabindex="-1" @click="go('shift-summary')">Summary</AppButton>
        <AppButton v-if="store.capabilities.can_close_shift" size="sm" variant="ghost" icon="check-circle" tabindex="-1" @click="go('shift-close')">Close shift</AppButton>
      </template>
      <AppButton v-else-if="shift.isStale" size="sm" variant="warning" icon="check-circle" tabindex="-1" @click="go('shift-close')">Close shift</AppButton>
      <AppButton v-else size="sm" icon="play-circle" tabindex="-1" @click="go('shift-open')">Open shift</AppButton>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import { useSessionStore } from '../../stores/session';
import { useShiftStore } from '../../stores/shift';
import { money, shortDate, time } from '../../utils/format';
import { AppButton, AppIcon } from '../ui';

// The shift on the Counter: is one open, what the drawer should hold now, and the
// way to an expense, the summary or the close, without leaving the screen.
defineProps<{ currency: string }>();
const emit = defineEmits<{ (e: 'expense'): void }>();

const store = useSessionStore();
const shift = useShiftStore();
const router = useRouter();
const route = useRoute();

// Shifts belong to a profile: a manager without one has none to show.
const visible = computed(() => shift.usesShifts && !!store.driverConfig && shift.loaded);
const canExpense = computed(() => store.capabilities.can_record_expense);
const toneClass = computed(() =>
  shift.isOpen ? 'bg-success/[0.07] text-foreground ring-success/25' : shift.isStale || shift.needsShift ? 'bg-danger/[0.07] text-danger ring-danger/25' : 'bg-warning/[0.08] text-foreground ring-warning/30',
);

const drawer = ref<number | null>(null);
/** Linked staff (overall shift) who have not closed their own shift yet. */
const linkedOut = ref<string[]>([]);
const drawerMode = ref('');
let seq = 0;
async function refresh() {
  await shift.refresh(true);
  await loadDrawer();
}
async function loadDrawer() {
  if (!shift.isOpen || store.capabilities.blind_shift_close) {
    drawer.value = null;
    return;
  }
  const mine = ++seq;
  try {
    const report = await api.getShiftSummary();
    if (mine !== seq) return;
    const row = report.payment_reconciliation.find((r) => r.mode_of_payment === report.cash_mode);
    drawer.value = row ? row.expected_amount : null;
    linkedOut.value = (report.linked?.open_shifts || []).map((s) => s.driver_name);
    drawerMode.value = report.cash_mode || '';
  } catch (_e) {
    if (mine === seq) drawer.value = null;
  }
}

function go(name: string) {
  router.push({ name, query: { back: route.name as string } });
}

watch(() => shift.active?.name, loadDrawer);
onMounted(refresh);
defineExpose({ refresh });
</script>
