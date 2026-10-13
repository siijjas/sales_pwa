<template>
  <span class="flex shrink-0 items-center justify-center rounded-2xl font-bold" :class="[sizeClass, toneClass]">
    {{ initials(name) }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { initials } from '../../utils/format';

const props = withDefaults(defineProps<{ name: string; size?: 'sm' | 'md' | 'lg'; tone?: 'primary' | 'neutral' | 'success' | 'danger' }>(), {
  size: 'md',
  tone: 'primary',
});
const sizeClass = computed(() => ({ sm: 'h-9 w-9 text-xs', md: 'h-11 w-11 text-sm', lg: 'h-14 w-14 text-lg' })[props.size]);
const toneClass = computed(
  () =>
    ({
      primary: 'bg-primary/12 text-primary',
      neutral: 'bg-card-muted text-muted',
      success: 'bg-success/14 text-success',
      danger: 'bg-danger/14 text-danger',
    })[props.tone],
);
</script>
