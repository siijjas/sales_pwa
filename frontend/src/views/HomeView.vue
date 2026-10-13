<template>
  <FleetHome v-if="store.isManager && !store.driverConfig" />
  <StaffHome v-else />
</template>

<script setup lang="ts">
import { useSessionStore } from '../stores/session';
import StaffHome from '../components/home/StaffHome.vue';
import FleetHome from '../components/home/FleetHome.vue';

const store = useSessionStore();
</script>
