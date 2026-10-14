<template>
  <BottomSheet :model-value="!!setup.sheet" :title="title" subtitle="Your own choice, kept on this device" size="lg" @update:model-value="(v) => !v && setup.close()">
    <div v-if="loading" class="py-6 text-center text-[13.5px] text-muted">Loading…</div>
    <AppAlert v-else-if="error" tone="danger" :message="error" />
    <div v-else-if="choices" class="space-y-5">
      <FormField label="Print format">
        <div class="grid gap-2 sm:grid-cols-2">
          <ChoiceCard v-for="f in choices.formats" :key="f.name" :selected="format === f.name" :title="f.name" @click="setup.set(choices.doctype, { format: f.name })">
            <template v-if="f.name === choices.default_format" #trailing>
              <StatusBadge tone="primary" :dot="false">Profile</StatusBadge>
            </template>
          </ChoiceCard>
        </div>
      </FormField>

      <FormField label="Where it prints">
        <div class="grid gap-2">
          <ChoiceCard :selected="printer === PDF" title="Open as PDF" subtitle="Shows the PDF in a new tab; print it from there." @click="setup.set(choices.doctype, { printer: PDF })">
            <template v-if="!choices.default_printer" #trailing>
              <StatusBadge tone="primary" :dot="false">Profile</StatusBadge>
            </template>
          </ChoiceCard>
          <ChoiceCard
            v-for="p in choices.printers"
            :key="p.name"
            :selected="printer === p.name"
            :title="p.name"
            :subtitle="p.printer_type === 'Receipt (ESC/POS)' ? 'Receipt printer' : 'Document printer'"
            @click="setup.set(choices.doctype, { printer: p.name })"
          >
            <template #trailing>
              <StatusBadge v-if="p.name === choices.default_printer" tone="primary" :dot="false" class="mr-1">Profile</StatusBadge>
              <StatusBadge :tone="p.online ? 'success' : 'warning'">{{ p.online ? 'Online' : 'Offline' }}</StatusBadge>
            </template>
          </ChoiceCard>
        </div>
        <p v-if="!choices.printers.length" class="mt-2 text-[12.5px] text-muted">
          No printer is set up yet. A manager adds them in the desk (Sales Print Agent, then Sales Printer) and runs the print agent at the shop.
        </p>
      </FormField>
    </div>

    <template #footer>
      <div class="flex gap-2">
        <AppButton v-if="setup.sheet?.name" size="lg" class="flex-1" icon="printer" :disabled="loading || !!error" @click="printNow">Print {{ setup.sheet.name }}</AppButton>
        <AppButton size="lg" :variant="setup.sheet?.name ? 'secondary' : 'primary'" :class="setup.sheet?.name ? '' : 'flex-1'" @click="setup.close()">Done</AppButton>
      </div>
    </template>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as api from '../api/frappe';
import type { PrintChoices } from '../types';
import { PDF, usePrintSetupStore } from '../stores/printSetup';
import { usePrint } from '../composables/usePrint';
import { AppAlert, AppButton, BottomSheet, ChoiceCard, FormField, StatusBadge } from './ui';

// One sheet in the shell (AppShell) for every screen: what a document prints with,
// and where, for the signed-in person. Opened through usePrint().choose(doctype).

const LABEL: Record<string, string> = {
  'Sales Order': 'Orders',
  'Sales Invoice': 'Invoices',
  'Payment Entry': 'Payment receipts',
  'Sales Shift Opening': 'Shift reports',
  'Sales Shift Closing': 'Shift reports',
};

const setup = usePrintSetupStore();
const { print } = usePrint();

const choices = ref<PrintChoices | null>(null);
const loading = ref(false);
const error = ref('');

const title = computed(() => `Printing · ${LABEL[setup.sheet?.doctype || ''] || setup.sheet?.doctype || ''}`);
const format = computed(() => (choices.value ? setup.prefFor(choices.value.doctype).format || choices.value.default_format : ''));
const printer = computed(() => (choices.value ? setup.prefFor(choices.value.doctype).printer || choices.value.default_printer || PDF : PDF));

watch(
  () => setup.sheet?.doctype,
  async (doctype) => {
    choices.value = null;
    error.value = '';
    if (!doctype) return;
    loading.value = true;
    try {
      const res = await api.getPrintChoices(doctype);
      if (setup.sheet?.doctype !== doctype) return;
      choices.value = res;
      // A printer that went away since it was chosen must not stay chosen.
      const chosen = setup.prefFor(doctype).printer;
      if (chosen && chosen !== PDF && !res.printers.some((p) => p.name === chosen)) setup.set(doctype, { printer: '' });
      const chosenFormat = setup.prefFor(doctype).format;
      if (chosenFormat && !res.formats.some((f) => f.name === chosenFormat)) setup.set(doctype, { format: '' });
    } catch (e: any) {
      error.value = e?.message || 'Could not load the printers';
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

function printNow() {
  const sheet = setup.sheet;
  if (!sheet?.name) return;
  // Inside the click, so a PDF's new tab is not blocked.
  void print(sheet.doctype, sheet.name, { isReturn: sheet.isReturn });
  setup.close();
}

function onKeydown(e: KeyboardEvent) {
  if (setup.sheet && e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    setup.close();
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown, true));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown, true));
</script>
