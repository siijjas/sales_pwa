<template>
  <component
    :is="to ? 'RouterLink' : 'button'"
    :to="to"
    :type="to ? undefined : 'button'"
    class="focus-ring flex min-h-[88px] flex-col items-start justify-between gap-3 rounded-3xl bg-card p-3.5 text-left shadow-card transition duration-150 ease-emphasis hover:shadow-raised active:scale-[0.97]"
    :class="disabled ? 'pointer-events-none opacity-50' : ''"
  >
    <span class="flex h-10 w-10 items-center justify-center rounded-2xl" :class="toneClass">
      <AppIcon :name="icon" :size="20" />
    </span>
    <span class="min-w-0">
      <span class="block truncate text-[14px] font-bold leading-tight text-foreground">{{ label }}</span>
      <span v-if="hint" class="mt-0.5 block truncate text-[11.5px] text-muted">{{ hint }}</span>
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';

const props = withDefaults(
  defineProps<{ label: string; icon: string; hint?: string; tone?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'; to?: string | object; disabled?: boolean }>(),
  { tone: 'primary' },
);
const toneClass = computed(
  () =>
    ({
      primary: 'bg-primary-soft text-primary',
      success: 'bg-success/14 text-success',
      warning: 'bg-warning/16 text-warning',
      danger: 'bg-danger/14 text-danger',
      info: 'bg-info/14 text-info',
      neutral: 'bg-card-muted text-muted',
    })[props.tone],
);
</script>
