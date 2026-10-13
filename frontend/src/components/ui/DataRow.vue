<template>
  <div class="flex items-center justify-between gap-4" :class="emphasis ? 'border-t border-line pt-3 text-[16px] font-bold text-foreground' : 'text-[14px] text-muted'">
    <span class="min-w-0 truncate"><slot name="label">{{ label }}</slot></span>
    <span class="tnum shrink-0 text-right" :class="[emphasis ? '' : 'font-medium text-foreground', valueClass]"><slot>{{ value }}</slot></span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label?: string; value?: string | number; emphasis?: boolean; valueClass?: string }>();
</script>
