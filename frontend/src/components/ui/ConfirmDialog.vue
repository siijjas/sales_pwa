<template>
  <BottomSheet :model-value="!!state.pending" size="sm" @update:model-value="(v: boolean) => !v && settle(false)">
    <div v-if="state.pending" class="space-y-5 pt-1">
      <div class="flex items-start gap-3.5">
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl" :class="iconClass">
          <AppIcon :name="state.pending.icon || (state.pending.tone === 'danger' ? 'alert' : 'info')" :size="22" />
        </span>
        <div class="min-w-0 pt-0.5">
          <h3 class="text-[17px] font-bold tracking-tight text-foreground">{{ state.pending.title }}</h3>
          <p v-if="state.pending.message" class="mt-1 text-[14px] leading-relaxed text-muted">{{ state.pending.message }}</p>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2.5">
        <AppButton variant="subtle" size="lg" block @click="settle(false)">{{ state.pending.cancelLabel }}</AppButton>
        <AppButton :variant="state.pending.tone === 'danger' ? 'danger' : state.pending.tone === 'warning' ? 'warning' : 'primary'" size="lg" block @click="settle(true)">
          {{ state.pending.confirmLabel }}
        </AppButton>
      </div>
    </div>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import BottomSheet from './BottomSheet.vue';
import AppButton from './AppButton.vue';
import AppIcon from './AppIcon.vue';
import { useConfirm } from '../../composables/useConfirm';

const { state, settle } = useConfirm();
const iconClass = computed(() =>
  state.pending?.tone === 'danger' ? 'bg-danger/14 text-danger' : state.pending?.tone === 'warning' ? 'bg-warning/16 text-warning' : 'bg-primary-soft text-primary',
);
</script>
