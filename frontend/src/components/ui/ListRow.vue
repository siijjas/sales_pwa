<template>
  <component
    :is="interactive ? 'button' : 'div'"
    :type="interactive ? 'button' : undefined"
    class="flex w-full items-center gap-3 px-4 py-3 text-left"
    :class="[interactive ? 'focus-ring transition hover:bg-card-muted/70 active:bg-card-muted' : '', dense ? 'min-h-[52px]' : 'min-h-[64px]']"
  >
    <slot name="leading">
      <span v-if="icon" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="iconClass">
        <AppIcon :name="icon" :size="19" />
      </span>
    </slot>
    <div class="min-w-0 flex-1">
      <p class="truncate text-[15px] font-semibold leading-tight text-foreground"><slot name="title">{{ title }}</slot></p>
      <p v-if="subtitle || $slots.subtitle" class="mt-0.5 truncate text-[12.5px] text-muted"><slot name="subtitle">{{ subtitle }}</slot></p>
    </div>
    <div v-if="$slots.trailing || chevron" class="flex shrink-0 items-center gap-2">
      <slot name="trailing" />
      <AppIcon v-if="chevron" name="chevron-right" :size="18" class="text-subtle" />
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import AppIcon from './AppIcon.vue';

const props = withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    icon?: string;
    tone?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';
    interactive?: boolean;
    chevron?: boolean;
    dense?: boolean;
  }>(),
  { tone: 'neutral' },
);

const iconClass = computed(
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
