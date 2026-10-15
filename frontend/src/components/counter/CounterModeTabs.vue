<template>
  <nav v-if="store.canCounterPurchase" class="inline-flex rounded-xl bg-card-muted p-0.5 text-[12.5px] font-semibold" aria-label="Counter screens">
    <RouterLink
      v-for="t in tabs"
      :key="t.name"
      :to="{ name: t.name }"
      tabindex="-1"
      class="rounded-[10px] px-3 py-1 transition"
      :class="route.name === t.name ? 'bg-elevated text-primary shadow-sm' : 'text-muted hover:text-foreground'"
    >
      {{ t.label }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router';
import { useSessionStore } from '../../stores/session';

// Sales and purchases are two screens of one Counter; each keeps its own cart.
const store = useSessionStore();
const route = useRoute();
const tabs = [
  { name: 'counter', label: 'Sales' },
  { name: 'counter-purchase', label: 'Purchases' },
];
</script>
