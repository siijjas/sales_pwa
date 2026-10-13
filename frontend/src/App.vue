<template>
  <RouterView v-if="route.meta.public" />
  <AppShell v-else>
    <RouterView v-slot="{ Component }">
      <component :is="Component" :key="pageKey" />
    </RouterView>
  </AppShell>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, RouterView } from 'vue-router';
import AppShell from './components/AppShell.vue';
import { useTheme } from './composables/useTheme';

const route = useRoute();
// Initialise the theme singleton + system-preference listener at app root.
useTheme();
// Re-mount a detail page when only its :name changes (order → order).
const pageKey = computed(() => `${String(route.name)}:${JSON.stringify(route.params)}`);
</script>
