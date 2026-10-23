<template>
  <WorkspacePage back :title="payment?.name || 'Payment'" :subtitle="payment?.party_name">
    <template #actions>
      <AppButton v-if="payment && payment.docstatus === 1" variant="secondary" size="sm" icon="printer" @click="printPdf">Print</AppButton>
    </template>

    <SkeletonList v-if="loading" :rows="2" height="6rem" />
    <AppAlert v-else-if="error" tone="danger" :message="error" />

    <div v-else-if="payment" class="space-y-4">
      <AppCard padding="lg" class="bg-success/12 ring-1 ring-inset ring-success/25">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.08em] text-success">Amount received</p>
            <p class="tnum mt-1 text-[32px] font-semibold leading-none tracking-tightest text-foreground">{{ currency }} {{ money(payment.paid_amount) }}</p>
          </div>
          <StatusBadge :status="payment.status" :dot="false" />
        </div>
        <p class="mt-3 text-[13px] text-muted">{{ relativeDate(payment.posting_date) }} · {{ payment.mode_of_payment }}</p>
      </AppCard>

      <AppAlert v-if="payment.docstatus === 2" tone="warning" message="This payment was cancelled." />
      <AppAlert v-if="payment.amended_from" tone="info" :message="`Corrected copy of ${payment.amended_from}.`" />
      <AppButton v-if="canChangeMode" variant="secondary" size="sm" icon="edit" @click="modeSheetOpen = true">Change payment mode</AppButton>

      <AppCard padding="none">
        <ListRow interactive chevron :title="payment.party_name" :subtitle="payment.party" @click="router.push({ name: 'customer', params: { name: payment.party } })">
          <template #leading><Avatar :name="payment.party_name || payment.party" size="sm" /></template>
        </ListRow>
      </AppCard>

      <AppCard class="space-y-2.5">
        <DataRow label="Date" :value="shortDate(payment.posting_date)" />
        <DataRow label="Mode of payment" :value="payment.mode_of_payment" />
        <DataRow label="Status" :value="payment.status" />
        <DataRow v-if="payment.reference_no" label="Reference no." :value="payment.reference_no" />
        <DataRow v-if="payment.reference_date" label="Reference date" :value="shortDate(payment.reference_date)" />
        <DataRow v-if="payment.unallocated_amount > 0" label="Unallocated (advance)" :value="`${currency} ${money(payment.unallocated_amount)}`" />
        <DataRow v-if="payment.remarks" label="Remarks" :value="payment.remarks" value-class="whitespace-normal text-left" />
      </AppCard>

      <section v-if="payment.references && payment.references.length">
        <SectionHeader title="Allocated to" />
        <AppCard padding="none" class="divide-y divide-line">
          <ListRow v-for="ref in payment.references" :key="ref.name" dense icon="file-text" tone="primary" :title="ref.reference_name" :subtitle="ref.reference_doctype">
            <template #trailing>
              <p class="tnum text-[14px] font-bold text-foreground">{{ currency }} {{ money(ref.allocated_amount) }}</p>
            </template>
          </ListRow>
        </AppCard>
      </section>
    </div>

    <PaymentModeSheet
      v-if="payment"
      v-model="modeSheetOpen"
      :payments="[{ name: payment.name, mode_of_payment: payment.mode_of_payment, paid_amount: payment.paid_amount }]"
      @changed="onModeChanged"
    />
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { getPaymentEntry } from '../api/frappe';
import { usePrint } from '../composables/usePrint';
import { useToast } from '../composables/useToast';
import type { PaymentModeChange } from '../types';
import PaymentModeSheet from '../components/PaymentModeSheet.vue';
import { money, relativeDate, shortDate } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, Avatar, DataRow, ListRow, SectionHeader, StatusBadge, SkeletonList } from '../components/ui';

const route = useRoute();
const router = useRouter();
const store = useSessionStore();
const currency = computed(() => store.currencyDisplay);
const payment = ref<any>(null);
const loading = ref(true);
const error = ref('');
const modeSheetOpen = ref(false);
const toast = useToast();

// Same rule as finance.change_payment_mode: a submitted collection or supplier payment,
// the user's own unless a manager. The server also refuses one a closed shift counted.
const canChangeMode = computed(() => {
  const p = payment.value;
  if (!p || p.docstatus !== 1) return false;
  const kind = `${p.payment_type}/${p.party_type}`;
  if (kind !== 'Receive/Customer' && kind !== 'Pay/Supplier') return false;
  return store.isManager || p.owner === store.session?.user;
});

async function load(name: string) {
  loading.value = true;
  try {
    payment.value = await getPaymentEntry(name);
  } catch (e: any) {
    error.value = e?.message || 'Payment not found';
  } finally {
    loading.value = false;
  }
}
onMounted(() => load(String(route.params.name)));

function onModeChanged(result: PaymentModeChange) {
  modeSheetOpen.value = false;
  toast.success(`Payment recorded as ${result.mode_of_payment}`, { message: `${result.name} replaces ${result.amended_from}.` });
  router.replace({ name: 'payment', params: { name: result.name } });
  load(result.name);
}

const { print } = usePrint();
const printPdf = () => payment.value && print('Payment Entry', payment.value.name);
</script>
