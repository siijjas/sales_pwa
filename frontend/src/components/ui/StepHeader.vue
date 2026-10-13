<template>
  <ol class="flex items-center gap-1.5">
    <li v-for="(step, i) in steps" :key="step" class="flex items-center gap-1.5">
      <span
        class="flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[11px] font-bold"
        :class="i < current ? 'bg-success/14 text-success' : i === current ? 'bg-primary text-primary-fg' : 'bg-card-muted text-subtle'"
      >
        <AppIcon v-if="i < current" name="check" :size="12" :stroke-width="3" />
        <template v-else>{{ i + 1 }}</template>
      </span>
      <span class="text-[12px] font-semibold" :class="i === current ? 'text-foreground' : 'hidden text-muted sm:inline'">{{ step }}</span>
      <span v-if="i < steps.length - 1" class="mx-0.5 h-px w-3 bg-line-strong" />
    </li>
  </ol>
</template>

<script setup lang="ts">
import AppIcon from './AppIcon.vue';
defineProps<{ steps: string[]; current: number }>();
</script>
