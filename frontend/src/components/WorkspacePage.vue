<template>
  <div class="min-h-full">
    <!-- Inner page: compact sticky bar with back, title and actions -->
    <div v-if="back" class="sticky top-0 z-40 bg-background/92 pt-safe backdrop-blur-md">
      <div class="mx-auto flex h-14 items-center gap-1 px-2 md:px-4" :class="containerClass">
        <button
          type="button"
          class="focus-ring flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-foreground transition hover:bg-card-muted active:scale-90"
          aria-label="Back"
          @click="goBack"
        >
          <AppIcon name="arrow-left" :size="21" />
        </button>
        <div class="min-w-0 flex-1 px-1">
          <h1 class="truncate text-[17px] font-bold leading-tight tracking-tight text-foreground">{{ title }}</h1>
          <p v-if="subtitle" class="truncate text-[12px] leading-tight text-muted">{{ subtitle }}</p>
        </div>
        <div v-if="$slots.actions" class="flex shrink-0 items-center gap-1.5 pr-1">
          <slot name="actions" />
        </div>
      </div>
      <div v-if="$slots.sticky" class="mx-auto px-4 pb-3 md:px-6" :class="containerClass">
        <slot name="sticky" />
      </div>
    </div>

    <!-- Top-level page: large title that scrolls, with an optional sticky strip below -->
    <template v-else>
      <div class="mx-auto px-4 pt-safe md:px-6" :class="containerClass">
        <div class="flex items-end justify-between gap-3 pb-3 pt-5 md:pt-8">
          <div class="min-w-0">
            <p v-if="eyebrow" class="text-[11px] font-bold uppercase tracking-[0.12em] text-primary">{{ eyebrow }}</p>
            <h1 class="truncate text-[26px] font-bold leading-tight tracking-tight text-foreground md:text-[30px]">{{ title }}</h1>
            <p v-if="subtitle" class="mt-0.5 text-[13px] text-muted">{{ subtitle }}</p>
          </div>
          <div v-if="$slots.actions" class="flex shrink-0 items-center gap-1.5">
            <slot name="actions" />
          </div>
        </div>
      </div>
      <div v-if="$slots.sticky" class="sticky top-0 z-40 bg-background/92 pt-safe backdrop-blur-md">
        <div class="mx-auto px-4 py-2 md:px-6" :class="containerClass">
          <slot name="sticky" />
        </div>
      </div>
    </template>

    <div class="mx-auto px-4 pb-6 pt-2 md:px-6" :class="containerClass">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter, type RouteLocationRaw } from 'vue-router';
import AppIcon from './ui/AppIcon.vue';

const props = withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    eyebrow?: string;
    width?: 'default' | 'wide' | 'narrow';
    /** true: go back in history. A route: go there instead (flows that must not return to a step). */
    back?: boolean | RouteLocationRaw;
  }>(),
  { width: 'default' },
);

const router = useRouter();
function goBack() {
  if (props.back && props.back !== true) router.replace(props.back);
  else if (window.history.length > 1) router.back();
  else router.replace({ name: 'home' });
}

const containerClass = computed(() => {
  if (props.width === 'narrow') return 'max-w-2xl';
  if (props.width === 'wide') return 'max-w-6xl';
  return 'max-w-3xl';
});
</script>
