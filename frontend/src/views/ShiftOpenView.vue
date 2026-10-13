<template>
  <WorkspacePage :back="{ name: 'shift' }" title="Open shift" subtitle="Declare the cash you start with">
    <SkeletonList v-if="loading" :rows="3" height="4rem" />

    <div v-else class="space-y-4 pb-28">
      <AppCard padding="lg" class="space-y-4">
        <div>
          <p class="text-[15px] font-bold text-foreground">Opening float by payment mode</p>
          <p class="mt-0.5 text-[13px] text-muted">What is in the drawer before the first sale. Leave a mode empty if you start with nothing in it.</p>
        </div>
        <FormField
          v-for="mode in modes"
          :key="mode.name"
          :label="mode.name"
          :hint="mode.type === 'Cash' ? 'Physical cash you are starting the day with.' : undefined"
        >
          <BaseInput v-model="floats[mode.name]" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" min="0" step="0.01" />
        </FormField>
        <div class="flex items-center justify-between rounded-2xl bg-card-muted px-4 py-3">
          <span class="text-[14px] font-semibold text-foreground">Total opening float</span>
          <span class="tnum text-[18px] font-bold text-foreground">{{ currency }} {{ money(totalFloat) }}</span>
        </div>
      </AppCard>

      <AppCard padding="lg">
        <FormField label="Notes" hint="Optional.">
          <BaseTextarea v-model="notes" :rows="2" placeholder="Anything to note about this shift…" />
        </FormField>
      </AppCard>

      <AppAlert v-if="error" tone="danger" :message="error" />
    </div>

    <StickyBar v-if="!loading">
      <AppButton size="lg" block icon="play-circle" :loading="submitting" @click="submit">
        {{ submitting ? 'Starting…' : 'Start shift' }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import { useShiftStore } from '../stores/shift';
import { useToast } from '../composables/useToast';
import { money } from '../utils/format';
import type { PaymentMode, ShiftBalanceDetail } from '../types';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, FormField, BaseInput, BaseTextarea, SkeletonList, StickyBar } from '../components/ui';

const store = useSessionStore();
const shift = useShiftStore();
const router = useRouter();
const toast = useToast();
const currency = computed(() => store.currencyDisplay);

const loading = ref(true);
const submitting = ref(false);
const error = ref('');
const modes = ref<PaymentMode[]>([]);
const floats = reactive<Record<string, number | string>>({});
const notes = ref('');

const totalFloat = computed(() => modes.value.reduce((sum, m) => sum + (Number(floats[m.name]) || 0), 0));

const load = async () => {
  try {
    // A shift is already open (or stale): the hub says what to do next.
    const active = await shift.refresh(true);
    if (active) {
      router.replace({ name: 'shift' });
      return;
    }
    modes.value = await api.getPaymentModes();
    modes.value.forEach((m) => {
      floats[m.name] = '';
    });
  } catch (e: any) {
    error.value = e?.message || 'Failed to load payment modes';
  } finally {
    loading.value = false;
  }
};

const submit = async () => {
  submitting.value = true;
  error.value = '';
  try {
    const balanceDetails: ShiftBalanceDetail[] = modes.value
      .map((m) => ({ mode_of_payment: m.name, opening_amount: Number(floats[m.name]) || 0 }))
      .filter((r) => r.opening_amount > 0);
    const opened = await api.openShift(balanceDetails, notes.value);
    shift.set(opened);
    toast.success('Shift started', { message: `Opening float ${currency.value} ${money(totalFloat.value)}` });
    router.replace({ name: 'home' });
  } catch (e: any) {
    error.value = e?.message || 'Failed to start shift';
  } finally {
    submitting.value = false;
  }
};

onMounted(load);
</script>
