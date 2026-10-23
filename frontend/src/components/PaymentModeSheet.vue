<template>
  <!--
    Correct the mode a payment was recorded under (card keyed in as cash, and so on).
    The server cancels the payment and submits an amended copy with the new mode.
  -->
  <BottomSheet
    :model-value="modelValue"
    title="Change payment mode"
    :subtitle="selected ? `${selected.name} · ${currency} ${money(selected.paid_amount)}` : undefined"
    @update:model-value="(v: boolean) => $emit('update:modelValue', v)"
  >
    <div class="space-y-5">
      <div v-if="payments.length > 1" class="space-y-3">
        <p class="text-xs font-bold uppercase tracking-wider text-muted">Which payment?</p>
        <ChoiceCard
          v-for="p in payments"
          :key="p.name"
          :selected="selectedName === p.name"
          :title="p.name"
          :subtitle="`${p.mode_of_payment} · ${currency} ${money(p.paid_amount)}`"
          @click="selectedName = p.name"
        />
      </div>

      <div v-if="selected" class="space-y-3">
        <div>
          <p class="text-xs font-bold uppercase tracking-wider text-muted">Recorded as {{ selected.mode_of_payment }}. Change to</p>
        </div>
        <SkeletonList v-if="loading" :rows="2" height="3.5rem" />
        <AppAlert v-else-if="!choices.length" tone="warning" message="No other payment mode is enabled on your profile." />
        <ChoiceCard
          v-for="m in choices"
          :key="m.name"
          :selected="mode === m.name"
          :title="m.name"
          :subtitle="m.type"
          @click="mode = m.name"
        />
      </div>

      <AppAlert tone="info" message="The payment is cancelled and replaced by a corrected copy with the same amount, date and invoices. Its shift counts it under the new mode." />
      <AppAlert v-if="error" tone="danger" :message="error" />
    </div>

    <template #footer>
      <div class="grid grid-cols-2 gap-2.5">
        <AppButton variant="subtle" size="lg" block @click="$emit('update:modelValue', false)">Cancel</AppButton>
        <AppButton size="lg" block icon="check" :loading="saving" :disabled="!selected || !mode || saving" @click="save">
          Change mode
        </AppButton>
      </div>
    </template>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import * as api from '../api/frappe';
import type { PaymentMode, PaymentModeChange, PaymentSummary } from '../types';
import { useSessionStore } from '../stores/session';
import { money } from '../utils/format';
import { AppAlert, AppButton, BottomSheet, ChoiceCard, SkeletonList } from './ui';

const props = defineProps<{ modelValue: boolean; payments: PaymentSummary[] }>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'changed', result: PaymentModeChange): void;
}>();

const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);

const modes = ref<PaymentMode[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const selectedName = ref('');
const mode = ref('');

const selected = computed(() => props.payments.find((p) => p.name === selectedName.value) || null);
const choices = computed(() => modes.value.filter((m) => m.name !== selected.value?.mode_of_payment));

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return;
    error.value = '';
    mode.value = '';
    selectedName.value = props.payments[0]?.name || '';
    if (modes.value.length) return;
    loading.value = true;
    modes.value = await api.getPaymentModes().catch(() => [] as PaymentMode[]);
    loading.value = false;
  },
  { immediate: true },
);
watch(selectedName, () => (mode.value = ''));

async function save() {
  if (!selected.value || !mode.value) return;
  saving.value = true;
  error.value = '';
  try {
    emit('changed', await api.changePaymentMode(selected.value.name, mode.value));
  } catch (e: any) {
    error.value = e?.message || 'Could not change the payment mode';
  } finally {
    saving.value = false;
  }
}
</script>
