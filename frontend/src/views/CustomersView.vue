<template>
  <WorkspacePage title="Customers" :subtitle="subtitle">
    <template #actions>
      <AppButton v-if="store.canCreateCustomer" size="sm" icon="plus" @click="openNew">New</AppButton>
    </template>
    <template #sticky>
      <SearchBar v-model="search" placeholder="Search by name, ID or mobile…" />
    </template>

    <AppAlert v-if="error" tone="danger" :message="error" class="mb-3" />
    <SkeletonList v-if="loading && !customers.length" :rows="6" height="4rem" />
    <EmptyState
      v-else-if="!customers.length"
      icon="users"
      title="No customers found"
      :description="search ? 'Try a different name, ID or mobile number.' : 'Customers you can sell to show up here.'"
    >
      <template v-if="store.canCreateCustomer" #action>
        <AppButton variant="secondary" icon="plus" @click="openNew">New customer</AppButton>
      </template>
    </EmptyState>
    <AppCard v-else padding="none" class="divide-y divide-line" :class="loading ? 'opacity-60' : ''">
      <ListRow
        v-for="c in customers"
        :key="c.name"
        interactive
        chevron
        :title="c.customer_name"
        :subtitle="rowSubtitle(c)"
        @click="open(c)"
      >
        <template #leading><Avatar :name="c.customer_name" size="sm" /></template>
        <template v-if="c.territory" #trailing>
          <StatusBadge tone="neutral" :dot="false">{{ c.territory }}</StatusBadge>
        </template>
      </ListRow>
    </AppCard>

    <BottomSheet v-model="newOpen" title="New customer">
      <div class="space-y-4">
        <FormField label="Customer name" required>
          <BaseInput v-model="newName" placeholder="e.g. Al Amal Grocery" @keyup.enter="submitNew" />
        </FormField>
        <FormField label="Mobile number">
          <BaseInput v-model="newMobile" type="tel" inputmode="tel" placeholder="Optional" @keyup.enter="submitNew" />
        </FormField>
        <AppAlert v-if="newError" tone="danger" :message="newError" />
      </div>
      <template #footer>
        <div class="grid grid-cols-2 gap-2.5">
          <AppButton variant="subtle" size="lg" block @click="newOpen = false">Cancel</AppButton>
          <AppButton size="lg" block :loading="creating" @click="submitNew">Add customer</AppButton>
        </div>
      </template>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import type { Customer } from '../types';
import { useSessionStore } from '../stores/session';
import { useToast } from '../composables/useToast';
import { plural } from '../utils/format';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, Avatar, ListRow, SearchBar, StatusBadge, SkeletonList, EmptyState, BottomSheet, FormField, BaseInput } from '../components/ui';

const router = useRouter();
const store = useSessionStore();
const toast = useToast();

const search = ref('');
const customers = ref<Customer[]>([]);
const loading = ref(true);
const error = ref('');

const subtitle = computed(() => (loading.value && !customers.value.length ? undefined : plural(customers.value.length, 'customer') + (search.value ? ' matching' : '')));

const rowSubtitle = (c: Customer) => [c.name !== c.customer_name ? c.name : '', c.territory, c.mobile_no].filter(Boolean).join(' · ');

let timer = 0;
let requestSeq = 0;
const load = async () => {
  const seq = ++requestSeq;
  loading.value = true;
  error.value = '';
  try {
    const rows = await api.searchCustomers(search.value);
    if (seq === requestSeq) customers.value = rows;
  } catch (e: any) {
    if (seq === requestSeq) error.value = e?.message || 'Could not load customers';
  } finally {
    if (seq === requestSeq) loading.value = false;
  }
};
watch(search, () => {
  window.clearTimeout(timer);
  timer = window.setTimeout(load, 300);
});
onMounted(load);

const open = (c: Customer) => router.push({ name: 'customer', params: { name: c.name } });

// New customer sheet (Sales Profile.allow_create_customer off: staff pick from the list only).
const newOpen = ref(false);
const newName = ref('');
const newMobile = ref('');
const newError = ref('');
const creating = ref(false);

const openNew = () => {
  newName.value = search.value.trim();
  newMobile.value = '';
  newError.value = '';
  newOpen.value = true;
};

const submitNew = async () => {
  const name = newName.value.trim();
  if (!name) {
    newError.value = 'Customer name is required';
    return;
  }
  creating.value = true;
  newError.value = '';
  try {
    const customer = await api.createCustomer(name, newMobile.value.trim() || undefined);
    newOpen.value = false;
    toast.success(`${customer.customer_name} added`);
    router.push({ name: 'customer', params: { name: customer.name } });
  } catch (e: any) {
    newError.value = e?.message || 'Failed to create customer';
  } finally {
    creating.value = false;
  }
};
</script>
