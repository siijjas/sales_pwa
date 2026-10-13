<template>
  <label class="flex cursor-pointer items-center justify-between gap-4 py-1" :class="disabled ? 'opacity-50' : ''">
    <span class="min-w-0">
      <span class="block text-[14px] font-semibold text-foreground">{{ label }}</span>
      <span v-if="hint" class="mt-0.5 block text-[12px] leading-snug text-muted">{{ hint }}</span>
    </span>
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :disabled="disabled"
      class="focus-ring relative h-7 w-12 shrink-0 rounded-full transition"
      :class="modelValue ? 'bg-primary' : 'bg-line-strong'"
      @click="$emit('update:modelValue', !modelValue)"
    >
      <span class="absolute top-0.5 h-6 w-6 rounded-full bg-white shadow-card transition" :class="modelValue ? 'left-[22px]' : 'left-0.5'" />
    </button>
  </label>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean; label: string; hint?: string; disabled?: boolean }>();
defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();
</script>
