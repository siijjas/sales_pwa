<template>
  <div class="flex min-h-dvh flex-col bg-background text-foreground" :style="{ '--tabbar-h': showTabs ? '72px' : '0px' }">
    <!-- Offline notice: the app is online-only, so say so instead of failing silently. -->
    <Transition name="fade">
      <div v-if="!isOnline" class="fixed inset-x-0 top-0 z-[90] bg-warning px-4 pb-2 pt-safe text-center text-[12px] font-bold text-warning-fg">
        <span class="inline-block pt-2">No connection. Changes cannot be saved until you are back online.</span>
      </div>
    </Transition>

    <!-- Rail: tablet and desktop -->
    <aside
      class="fixed inset-y-0 left-0 z-40 hidden w-[84px] flex-col items-center bg-elevated pb-4 pt-safe shadow-[1px_0_0_rgb(var(--c-line))] md:flex"
    >
      <RouterLink :to="{ name: 'home' }" class="mt-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-fg shadow-btn" aria-label="Home">
        <AppIcon :name="brandIcon" :size="22" />
      </RouterLink>
      <nav class="mt-6 flex w-full flex-1 flex-col items-center gap-1">
        <RouterLink
          v-for="item in nav.primary"
          :key="item.name"
          :to="item.to"
          class="group flex w-[68px] flex-col items-center gap-1 rounded-2xl py-2 text-[10.5px] font-semibold transition"
          :class="isActive(item.names) ? 'bg-primary-soft text-primary' : 'text-subtle hover:bg-card-muted hover:text-foreground'"
        >
          <AppIcon :name="item.icon" :size="21" :stroke-width="isActive(item.names) ? 2.3 : 2" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <ThemeToggle class="mb-2" />
      <button class="flex w-[68px] flex-col items-center gap-1 rounded-2xl py-2 text-[10.5px] font-semibold text-subtle transition hover:text-danger" @click="logout">
        <AppIcon name="logout" :size="20" />
        Sign out
      </button>
    </aside>

    <main class="w-full min-w-0 flex-1 md:pl-[84px]" :style="{ paddingBottom: 'calc(var(--tabbar-h) + env(safe-area-inset-bottom))' }">
      <slot />
    </main>

    <!-- Tabs: phone -->
    <nav
      v-if="showTabs"
      class="fixed bottom-0 left-0 right-0 z-40 flex h-[calc(72px+env(safe-area-inset-bottom))] items-start justify-around bg-elevated/95 pb-safe pt-1.5 backdrop-blur-md shadow-[0_-1px_0_rgb(var(--c-line))] md:hidden"
    >
      <RouterLink
        v-for="item in nav.primary"
        :key="item.name"
        :to="item.to"
        class="group flex min-w-0 flex-1 flex-col items-center gap-[3px] py-1 text-[10.5px]"
        :class="isActive(item.names) ? 'font-bold text-primary' : 'font-medium text-subtle'"
      >
        <span class="flex h-8 w-[52px] items-center justify-center rounded-xl transition duration-150 ease-emphasis" :class="isActive(item.names) ? 'bg-primary-soft' : 'group-active:scale-90'">
          <AppIcon :name="item.icon" :size="22" :stroke-width="isActive(item.names) ? 2.3 : 2" />
        </span>
        <span class="truncate">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <ToastHost />
    <ConfirmDialog />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { useNavigation } from '../navigation';
import { useToast } from '../composables/useToast';
import { AppIcon, ThemeToggle, ToastHost, ConfirmDialog } from './ui';

const store = useSessionStore();
const route = useRoute();
const router = useRouter();
const toast = useToast();

const nav = computed(() => useNavigation());
const brandIcon = computed(() => (store.isManager && !store.driverConfig ? 'activity' : store.isFieldSales ? 'users' : 'truck'));
// Flows (sale steps, shift open/close) hide the tabs so the primary action owns the bottom edge.
const showTabs = computed(() => route.meta.tabs !== false);

const isOnline = ref(navigator.onLine);
const handleOnline = () => (isOnline.value = true);
const handleOffline = () => (isOnline.value = false);
onMounted(() => {
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
});
onUnmounted(() => {
  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);
});

function isActive(names: string[]) {
  return names.includes(String(route.name || ''));
}

async function logout() {
  const warning = await store.logout();
  if (warning) toast.warning('Signed out locally', { message: warning });
  router.push({ name: 'login' });
}
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
</style>
