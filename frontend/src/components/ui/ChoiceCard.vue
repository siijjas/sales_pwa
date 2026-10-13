<template>
  <button
    type="button"
    class="focus-ring flex w-full items-center gap-3 rounded-2xl p-3.5 text-left ring-1 ring-inset transition"
    :class="selected ? 'bg-primary/[0.06] ring-primary/50' : 'bg-card ring-line hover:bg-card-muted/60'"
    :disabled="disabled"
  >
    <span
      class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition"
      :class="selected ? 'border-primary bg-primary text-primary-fg' : 'border-line-strong'"
    >
      <AppIcon v-if="selected" name="check" :size="12" :stroke-width="3.5" />
    </span>
    <span class="min-w-0 flex-1">
      <span class="block truncate text-[15px] font-semibold text-foreground"><slot name="title">{{ title }}</slot></span>
      <span v-if="subtitle || $slots.subtitle" class="block truncate text-[12.5px] text-muted"><slot name="subtitle">{{ subtitle }}</slot></span>
    </span>
    <slot name="trailing" />
  </button>
</template>

<script setup lang="ts">
import AppIcon from './AppIcon.vue';
defineProps<{ title?: string; subtitle?: string; selected?: boolean; disabled?: boolean }>();
</script>
