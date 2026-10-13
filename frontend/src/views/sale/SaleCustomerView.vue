<template>
  <WorkspacePage :back="{ name: 'home' }" title="New sale" subtitle="Who is this sale for?">
    <template #actions>
      <AppButton v-if="store.canCreateCustomer" size="sm" variant="secondary" icon="plus" @click="openNewCustomer">New</AppButton>
    </template>
    <template #sticky>
      <div class="space-y-2.5">
        <StepHeader :steps="STEPS" :current="0" />
        <SearchBar v-model="search" placeholder="Search by name, ID or mobile…" />
      </div>
    </template>

    <div class="space-y-4">
      <AppAlert v-if="error" tone="danger" :message="error" />

      <!-- A draft already names a customer: offer to carry on with it. -->
      <AppCard v-if="sale.customer && !search" padding="none">
        <ListRow interactive chevron :title="`Continue with ${sale.customer.customer_name}`" :subtitle="continueSubtitle" @click="router.push({ name: sale.lines.length ? 'sell-review' : 'sell-items' })">
          <template #leading><Avatar :name="sale.customer.customer_name" /></template>
        </ListRow>
      </AppCard>

      <SkeletonList v-if="loading" :rows="6" height="4rem" />
      <EmptyState v-else-if="!customers.length" icon="users" title="No customers found" :description="search ? 'Try a different name, ID or mobile number.' : 'No customers are available to you.'">
        <template v-if="store.canCreateCustomer" #action>
          <AppButton variant="secondary" icon="plus" @click="openNewCustomer">Add “{{ search || 'new customer' }}”</AppButton>
        </template>
      </EmptyState>
      <AppCard v-else padding="none" class="divide-y divide-line">
        <ListRow
          v-for="customer in customers"
          :key="customer.name"
          interactive
          chevron
          :title="customer.customer_name"
          :subtitle="subtitleFor(customer)"
          @click="select(customer)"
        >
          <template #leading><Avatar :name="customer.customer_name" /></template>
          <template v-if="customer.territory" #trailing>
            <StatusBadge tone="neutral" :dot="false">{{ customer.territory }}</StatusBadge>
          </template>
        </ListRow>
      </AppCard>
    </div>

    <BottomSheet v-model="newCustomerOpen" title="New customer">
      <div class="space-y-4">
        <FormField label="Customer name" required>
          <BaseInput v-model="newCustomerName" placeholder="e.g. Al Amal Grocery" @keyup.enter="submitNewCustomer" />
        </FormField>
        <FormField label="Mobile number">
          <BaseInput v-model="newCustomerMobile" type="tel" inputmode="tel" placeholder="Optional" @keyup.enter="submitNewCustomer" />
        </FormField>
        <AppAlert v-if="newCustomerError" tone="danger" :message="newCustomerError" />
      </div>
      <template #footer>
        <div class="grid grid-cols-2 gap-2.5">
          <AppButton variant="subtle" size="lg" block @click="newCustomerOpen = false">Cancel</AppButton>
          <AppButton size="lg" block :loading="creatingCustomer" @click="submitNewCustomer">Add customer</AppButton>
        </div>
      </template>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import type { Customer } from '../../types';
import { useSessionStore } from '../../stores/session';
import { useSaleStore } from '../../stores/sale';
import { useShiftStore } from '../../stores/shift';
import { useToast } from '../../composables/useToast';
import { money, plural } from '../../utils/format';
import WorkspacePage from '../../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, Avatar, BaseInput, BottomSheet, EmptyState, FormField, ListRow, SearchBar, SkeletonList, StatusBadge, StepHeader } from '../../components/ui';

const STEPS = ['Customer', 'Items', 'Review'];

const store = useSessionStore();
const sale = useSaleStore();
const shift = useShiftStore();
const router = useRouter();
const route = useRoute();
const toast = useToast();

const search = ref('');
const customers = ref<Customer[]>([]);
const loading = ref(true);
const error = ref('');

const newCustomerOpen = ref(false);
const newCustomerName = ref('');
const newCustomerMobile = ref('');
const newCustomerError = ref('');
const creatingCustomer = ref(false);

const continueSubtitle = computed(() =>
  sale.lines.length ? `${plural(sale.lines.length, 'item')} · ${store.currencyDisplay} ${money(sale.subtotal)}` : 'No items yet',
);

const subtitleFor = (c: Customer) => [c.name, c.mobile_no].filter(Boolean).join(' · ');

let timer = 0;
const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    customers.value = await api.searchCustomers(search.value);
  } catch (e: any) {
    error.value = e?.message || 'Could not load customers';
  } finally {
    loading.value = false;
  }
};
watch(search, () => {
  clearTimeout(timer);
  timer = window.setTimeout(load, 300);
});

function select(customer: Customer) {
  sale.setCustomer(customer);
  router.push({ name: 'sell-items' });
}

function openNewCustomer() {
  newCustomerName.value = search.value.trim();
  newCustomerMobile.value = '';
  newCustomerError.value = '';
  newCustomerOpen.value = true;
}

async function submitNewCustomer() {
  const name = newCustomerName.value.trim();
  if (!name) {
    newCustomerError.value = 'Customer name is required';
    return;
  }
  creatingCustomer.value = true;
  newCustomerError.value = '';
  try {
    const customer = await api.createCustomer(name, newCustomerMobile.value.trim() || undefined);
    newCustomerOpen.value = false;
    toast.success(`${customer.customer_name} added`);
    select(customer);
  } catch (e: any) {
    newCustomerError.value = e?.message || 'Failed to create customer';
  } finally {
    creatingCustomer.value = false;
  }
}

onMounted(async () => {
  await shift.refresh();
  if (shift.needsShift) {
    toast.warning(shift.isStale ? 'Close your earlier shift first' : 'Open your shift to start selling');
    router.replace(shift.gateRoute);
    return;
  }
  // Arriving from a customer page: skip the pick.
  const preset = typeof route.query.customer === 'string' ? route.query.customer : '';
  if (preset) {
    try {
      const customer = await api.getCustomer(preset);
      select(customer);
      return;
    } catch (e: any) {
      error.value = e?.message || 'Customer not found';
    }
  }
  load();
});
</script>
