<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modelValue" class="fixed inset-0 z-[100] flex items-end justify-center sm:items-center sm:p-6" @keydown.esc="close">
        <div class="absolute inset-0 bg-[rgb(23_26_27/0.55)] backdrop-blur-sm" @click="close" />
        <div
          class="relative flex w-full flex-col rounded-t-4xl bg-elevated shadow-pop sm:rounded-3xl"
          :class="sizeClass"
          role="dialog"
          aria-modal="true"
        >
          <div class="mx-auto mt-3 h-[5px] w-10 shrink-0 rounded-full bg-line-strong sm:hidden" />
          <div v-if="title || $slots.header || back" class="flex shrink-0 items-center gap-2 px-5 pb-2 pt-3">
            <button
              v-if="back"
              type="button"
              class="-ml-2 flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full text-muted transition hover:bg-card-muted hover:text-foreground"
              aria-label="Back"
              @click="$emit('back')"
            >
              <AppIcon name="arrow-left" :size="18" />
            </button>
            <div class="min-w-0 flex-1">
              <slot name="header">
                <h3 class="truncate text-[17px] font-bold tracking-tight text-foreground">{{ title }}</h3>
                <p v-if="subtitle" class="truncate text-[12px] text-muted">{{ subtitle }}</p>
              </slot>
            </div>
            <button
              type="button"
              class="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-card-muted text-muted transition hover:text-foreground"
              aria-label="Close"
              @click="close"
            >
              <AppIcon name="x" :size="18" />
            </button>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5" :class="$slots.footer ? '' : 'pb-safe'">
            <div :class="title || $slots.header ? 'pt-2' : 'pt-4'">
              <slot />
            </div>
          </div>
          <div v-if="$slots.footer" class="shrink-0 border-t border-line bg-elevated px-5 pb-safe pt-3 sm:rounded-b-3xl">
            <div class="pb-3">
              <slot name="footer" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import AppIcon from './AppIcon.vue';

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title?: string;
    subtitle?: string;
    /** sm: short prompts · md: forms · lg: tall content (scrolls) · full: near full-height. */
    size?: 'sm' | 'md' | 'lg' | 'full';
    /** Show a back arrow in the header (multi-step sheets). */
    back?: boolean;
  }>(),
  { size: 'md' },
);
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void; (e: 'back'): void }>();

const sizeClass = computed(
  () =>
    ({
      sm: 'max-h-[70dvh] sm:max-w-sm',
      md: 'max-h-[85dvh] sm:max-w-md',
      lg: 'max-h-[92dvh] sm:max-w-lg',
      full: 'h-[96dvh] sm:h-[90dvh] sm:max-w-2xl',
    })[props.size],
);

function close() {
  emit('update:modelValue', false);
}

// Keep the page from scrolling behind an open sheet.
watch(
  () => props.modelValue,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : '';
  },
);
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.fade-enter-active > div:last-child {
  animation: sheet-up 0.28s cubic-bezier(0.2, 0.8, 0.2, 1);
}
</style>
