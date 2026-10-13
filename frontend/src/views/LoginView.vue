<template>
  <div class="relative flex min-h-dvh flex-col bg-background px-5 pb-8 pt-safe">
    <div class="absolute right-4 top-4 pt-safe">
      <ThemeToggle />
    </div>

    <div class="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
      <div class="mb-8 flex flex-col items-start gap-4">
        <div class="flex h-14 w-14 items-center justify-center rounded-3xl bg-primary text-primary-fg shadow-raised">
          <AppIcon name="truck" :size="28" />
        </div>
        <div>
          <p class="text-[11px] font-bold uppercase tracking-[0.3em] text-primary">Sales App</p>
          <h1 class="mt-1 text-[28px] font-bold leading-tight tracking-tight text-foreground">Sign in to start your day</h1>
          <p class="mt-1.5 text-[14px] leading-relaxed text-muted">Orders, collections, stock and shifts for van and field sales. Use your ERPNext username and password.</p>
        </div>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <FormField label="Username">
          <BaseInput v-model="username" icon="user" placeholder="you@company.com" autocomplete="username" />
        </FormField>
        <FormField label="Password">
          <BaseInput v-model="password" type="password" icon="lock" placeholder="••••••••" autocomplete="current-password" />
        </FormField>
        <AppAlert v-if="error" tone="danger" :message="error" />
        <AppButton type="submit" size="lg" block :loading="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </AppButton>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';
import { AppButton, AppAlert, AppIcon, FormField, BaseInput, ThemeToggle } from '../components/ui';

const store = useSessionStore();
const router = useRouter();
const route = useRoute();

const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

const submit = async () => {
  if (!username.value || !password.value) {
    error.value = 'Enter your username and password.';
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    await store.login(username.value, password.value);
    const next = typeof route.query.next === 'string' ? route.query.next : null;
    router.replace(next || { name: 'home' });
  } catch (e: any) {
    error.value = e?.message || 'Login failed';
  } finally {
    loading.value = false;
  }
};
</script>
