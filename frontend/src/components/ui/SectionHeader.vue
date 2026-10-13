<template>
  <div class="mb-2.5 flex items-end justify-between gap-3 px-0.5">
    <div class="min-w-0">
      <p class="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">{{ title }}</p>
      <p v-if="description" class="mt-0.5 text-[12px] text-subtle">{{ description }}</p>
    </div>
    <button v-if="actionLabel" type="button" class="shrink-0 text-[13px] font-semibold text-primary" @click="$emit('action')">
      {{ actionLabel }}
    </button>
    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; description?: string; actionLabel?: string }>();
defineEmits<{ (e: 'action'): void }>();
</script>
