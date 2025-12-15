<template>
  <div class="h-full flex flex-col items-center justify-center px-6">
    <div class="w-full max-w-sm space-y-6">
      <div class="text-center space-y-2">
        <div class="mx-auto h-14 w-14 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600">
          <span class="font-bold text-lg">PWA</span>
        </div>
        <h2 class="text-2xl font-bold text-gray-900">ERPNext Sales</h2>
        <p class="text-sm text-gray-600">Sign in with your ERPNext credentials</p>
      </div>
      <form @submit.prevent="submit" class="space-y-4">
        <div class="space-y-2">
          <input
            v-model="username"
            class="w-full rounded-lg border px-3 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            placeholder="Username"
            required
          />
          <input
            v-model="password"
            type="password"
            class="w-full rounded-lg border px-3 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            placeholder="Password"
            required
          />
        </div>
        <button
          class="w-full bg-blue-600 text-white rounded-lg py-3 font-semibold disabled:opacity-50"
          :disabled="loading"
          type="submit"
        >
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
      <p v-if="error" class="text-sm text-red-600 text-center">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSessionStore } from '../stores/session';

const store = useSessionStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

const submit = async () => {
  loading.value = true;
  error.value = '';
  try {
    await store.login(username.value, password.value);
    router.push({ name: 'dashboard' });
  } catch (e: any) {
    error.value = e?.message || 'Login failed';
  } finally {
    loading.value = false;
  }
};
</script>
