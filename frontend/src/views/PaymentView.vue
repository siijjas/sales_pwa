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
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { getPaymentEntry, downloadPdf } from '../api/frappe';
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

onMounted(async () => {
  try {
    payment.value = await getPaymentEntry(String(route.params.name));
  } catch (e: any) {
    error.value = e?.message || 'Payment not found';
  } finally {
    loading.value = false;
  }
});

const printPdf = () => payment.value && downloadPdf('Payment Entry', payment.value.name);
</script>
