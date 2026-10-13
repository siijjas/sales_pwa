<template>
  <WorkspacePage title="More" :subtitle="store.session?.full_name">
    <div class="space-y-5">
      <AppCard padding="sm">
        <div class="flex items-center gap-3">
          <Avatar :name="store.session?.full_name || ''" />
          <div class="min-w-0 flex-1">
            <p class="truncate font-bold text-foreground">{{ store.session?.full_name }}</p>
            <p class="truncate text-xs text-muted">{{ store.workspaceLabel }}<template v-if="warehouse"> · {{ warehouse }}</template></p>
          </div>
          <StatusBadge v-if="store.isManager" tone="primary" :dot="false">Manager</StatusBadge>
        </div>
      </AppCard>

      <section v-if="nav.work.length">
        <SectionHeader title="Work" />
        <AppCard padding="none" class="divide-y divide-line">
          <ListRow v-for="item in nav.work" :key="item.name" interactive chevron :icon="item.icon" tone="primary" :title="item.label" :subtitle="item.hint" @click="router.push(item.to)" />
        </AppCard>
      </section>

      <section v-if="nav.manage.length">
        <SectionHeader title="Manage" />
        <AppCard padding="none" class="divide-y divide-line">
          <ListRow v-for="item in nav.manage" :key="item.name" interactive chevron :icon="item.icon" tone="info" :title="item.label" :subtitle="item.hint" @click="router.push(item.to)" />
        </AppCard>
      </section>

      <section>
        <SectionHeader title="App" />
        <AppCard padding="none" class="divide-y divide-line">
          <div class="px-4 py-3">
            <ListRow icon="moon" tone="neutral" title="Appearance" :subtitle="`Currently ${preference === 'system' ? 'following the device' : preference}`" dense class="!px-0 !py-0" />
            <SegmentedControl :model-value="preference" :options="[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'Follow device' }]" class="mt-3" @update:model-value="(v: string) => setPreference(v as any)" />
          </div>
          <ListRow interactive icon="logout" tone="danger" title="Sign out" @click="logout" />
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { useNavigation } from '../navigation';
import { useTheme } from '../composables/useTheme';
import { useToast } from '../composables/useToast';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, Avatar, ListRow, SectionHeader, SegmentedControl, StatusBadge } from '../components/ui';

const store = useSessionStore();
const router = useRouter();
const toast = useToast();
const nav = computed(() => useNavigation());
const { preference, setPreference } = useTheme();
const warehouse = computed(() => store.driverConfig?.selling_warehouse || store.driverConfig?.stock_warehouse || '');

async function logout() {
  const warning = await store.logout();
  if (warning) toast.warning('Signed out locally', { message: warning });
  router.push({ name: 'login' });
}
</script>
