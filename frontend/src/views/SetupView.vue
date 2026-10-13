<template>
  <WorkspacePage eyebrow="Manager" title="Setup" subtitle="How invoicing, staff and the app are configured">
    <div class="space-y-5">
      <section>
        <SectionHeader title="Configuration" />
        <AppCard padding="none" class="divide-y divide-line">
          <ListRow interactive chevron icon="file-text" tone="primary" title="Invoice options" subtitle="Numbering series, tax template and payment rule per option. Enabled per Sales Profile." @click="router.push({ name: 'invoice-options' })" />
          <ListRow interactive chevron icon="user" tone="info" title="Staff profiles" subtitle="Warehouses, payment modes, cash rules and who is assigned." @click="router.push({ name: 'staff' })" />
        </AppCard>
      </section>

      <section>
        <SectionHeader title="Appearance" />
        <AppCard padding="lg">
          <p class="text-[14px] font-semibold text-foreground">Theme</p>
          <p class="mt-0.5 text-[12.5px] text-muted">Applies to this device only.</p>
          <SegmentedControl class="mt-3" :model-value="preference" :options="[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'Follow device' }]" @update:model-value="(v: string) => setPreference(v as ThemePreference)" />
        </AppCard>
      </section>

      <section>
        <SectionHeader title="How access works" />
        <AppAlert tone="info" title="Three roles">
          <span class="block"><span class="font-semibold">System Manager</span> — full control, including deleting configuration.</span>
          <span class="mt-1 block"><span class="font-semibold">Sales Manager</span> — runs the fleet: profiles, invoice options, reports, closing and reopening shifts.</span>
          <span class="mt-1 block"><span class="font-semibold">Sales App User</span> — granted automatically to anyone assigned to an active Sales Profile; sees only their own work.</span>
        </AppAlert>
      </section>

      <section>
        <SectionHeader title="About" />
        <AppCard padding="none">
          <ListRow icon="briefcase" tone="neutral" title="Sales App" :subtitle="`Signed in as ${store.session?.full_name || store.session?.user}`" />
        </AppCard>
      </section>
    </div>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { useTheme, type ThemePreference } from '../composables/useTheme';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppAlert, ListRow, SectionHeader, SegmentedControl } from '../components/ui';

const router = useRouter();
const store = useSessionStore();
const { preference, setPreference } = useTheme();
</script>
