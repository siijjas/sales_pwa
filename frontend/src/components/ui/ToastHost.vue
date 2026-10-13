<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed inset-x-0 top-0 z-[120] flex flex-col items-center gap-2 px-4 pt-safe">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="pointer-events-auto mt-3 flex w-full max-w-md items-start gap-3 rounded-2xl bg-elevated px-4 py-3 shadow-pop ring-1 ring-inset ring-line"
          role="status"
        >
          <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full" :class="toneClass[t.tone]">
            <AppIcon :name="toneIcon[t.tone]" :size="15" :stroke-width="2.5" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="text-[14px] font-semibold leading-snug text-foreground">{{ t.title }}</p>
            <p v-if="t.message" class="mt-0.5 text-[13px] leading-snug text-muted">{{ t.message }}</p>
            <button v-if="t.action" type="button" class="mt-1.5 text-[13px] font-bold text-primary" @click="run(t)">
              {{ t.action.label }}
            </button>
          </div>
          <button type="button" class="-mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-subtle hover:text-foreground" aria-label="Dismiss" @click="dismiss(t.id)">
            <AppIcon name="x" :size="15" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import AppIcon from './AppIcon.vue';
import { useToast, type Toast } from '../../composables/useToast';

const { toasts, dismiss } = useToast();

const toneClass = {
  success: 'bg-success/14 text-success',
  danger: 'bg-danger/14 text-danger',
  warning: 'bg-warning/16 text-warning',
  info: 'bg-info/14 text-info',
};
const toneIcon = { success: 'check', danger: 'alert', warning: 'alert', info: 'info' };

function run(t: Toast) {
  t.action?.run();
  dismiss(t.id);
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.98);
}
</style>
