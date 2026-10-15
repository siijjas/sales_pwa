<template>
  <BottomSheet :model-value="!!setup.sheet" :title="title" subtitle="Choose the format and where it prints" size="lg" @update:model-value="(v) => !v && setup.close()">
    <div v-if="loading" class="py-6 text-center text-[13.5px] text-muted">Loading…</div>
    <AppAlert v-else-if="error" tone="danger" :message="error" />
    <div v-else-if="choices" class="space-y-5">
      <FormField label="Print format">
        <div class="grid gap-2 sm:grid-cols-2">
          <ChoiceCard v-for="f in choices.formats" :key="f.name" :selected="format === f.name" :title="f.name" @click="pick({ format: f.name })">
            <template v-if="f.name === choices.default_format" #trailing>
              <StatusBadge tone="primary" :dot="false">Profile</StatusBadge>
            </template>
          </ChoiceCard>
        </div>
      </FormField>

      <FormField label="Where it prints">
        <div class="grid grid-cols-1 gap-2">
          <ChoiceCard :selected="printer === PDF" title="Open as PDF" subtitle="Shows the PDF in a new tab; print it from there." @click="pick({ printer: PDF })">
            <template v-if="!profilePrinter" #trailing>
              <StatusBadge tone="primary" :dot="false">Profile</StatusBadge>
            </template>
          </ChoiceCard>
          <ChoiceCard
            v-for="p in choices.printers"
            :key="p.name"
            :selected="printer === p.name"
            :title="p.name"
            :subtitle="p.printer_type === 'Receipt (ESC/POS)' ? 'Receipt printer' : 'Document printer'"
            @click="pick({ printer: p.name })"
          >
            <template #trailing>
              <StatusBadge v-if="p.name === profilePrinter" tone="primary" :dot="false" class="mr-1">Profile</StatusBadge>
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
        <AppButton data-print-now size="lg" class="flex-1" :icon="printer === PDF ? 'file-text' : 'printer'" :disabled="!choices || !format" @click="printNow">
          {{ printer === PDF ? 'Open PDF' : 'Print' }} <kbd class="ml-1 text-[11px] opacity-70">Enter</kbd>
        </AppButton>
        <AppButton size="lg" variant="secondary" @click="setup.close()">Cancel</AppButton>
      </div>
    </template>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as api from '../api/frappe';
import type { PrintChoices } from '../types';
import { PDF, type PrintPreference, usePrintSetupStore } from '../stores/printSetup';
import { usePrint } from '../composables/usePrint';
import { AppAlert, AppButton, BottomSheet, ChoiceCard, FormField, StatusBadge } from './ui';

// One sheet in the shell (AppShell) for every screen. Each Print tap opens it
// (usePrint().print) to pick the format and the printer, or the PDF, for that print.
// It opens on what this person picked last for the document type, else on the
// screen's suggested format and the profile's printer, so Enter alone prints.

const setup = usePrintSetupStore();
const { send, profilePrinterFor } = usePrint();

const choices = ref<PrintChoices | null>(null);
const loading = ref(false);
const error = ref('');
const format = ref('');
const printer = ref<string>(PDF);

const title = computed(() => (setup.sheet ? `Print ${setup.sheet.name}` : 'Print'));
/** The printer the profile would use, marked in the list: the person's own profile first (it knows credit notes), else the server's answer. */
const profilePrinter = computed(() => {
  const sheet = setup.sheet;
  if (!sheet || !choices.value) return null;
  const own = profilePrinterFor(sheet.doctype, sheet.isReturn);
  return own && choices.value.printers.some((p) => p.name === own) ? own : choices.value.default_printer;
});

watch(
  () => setup.sheet,
  async (sheet) => {
    choices.value = null;
    error.value = '';
    if (!sheet) return;
    loading.value = true;
    try {
      const res = await api.getPrintChoices(sheet.doctype);
      if (setup.sheet !== sheet) return;
      choices.value = res;
      // Start on the last pick while its format and printer still exist, else on the suggestions.
      const last = setup.lastFor(sheet.doctype);
      const formatOk = (f: string | null | undefined) => !!f && res.formats.some((x) => x.name === f);
      const printerOk = (p: string) => p === PDF || res.printers.some((x) => x.name === p);
      format.value = [last.format, sheet.format, res.default_format].find(formatOk) || res.formats[0]?.name || '';
      printer.value = [last.printer, profilePrinter.value || ''].find((p) => !!p && printerOk(p)) || PDF;
      focusPrint();
    } catch (e: any) {
      error.value = e?.message || 'Could not load the printers';
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

function focusPrint() {
  void nextTick(() => document.querySelector<HTMLButtonElement>('[data-print-now]')?.focus());
}

function pick(change: Partial<PrintPreference>) {
  if (change.format !== undefined) format.value = change.format;
  if (change.printer !== undefined) printer.value = change.printer;
  focusPrint();
}

function printNow() {
  const sheet = setup.sheet;
  if (!sheet || !choices.value) return;
  const pref = { format: format.value, printer: printer.value };
  setup.remember(sheet.doctype, pref);
  setup.close();
  // Inside the click or keypress, so a PDF's new tab is not blocked.
  void send(sheet.doctype, sheet.name, pref.format, pref.printer, sheet.isReturn);
}

// The sheet owns the keyboard while open: Enter prints (unless it lands on one of the
// sheet's own buttons, which then do their own thing), Escape cancels. Captured, so the
// Counter's customer and item boxes behind it never see the key.
function onKeydown(e: KeyboardEvent) {
  if (!setup.sheet) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    setup.close();
  } else if (e.key === 'Enter') {
    const target = e.target as HTMLElement;
    if (target.tagName === 'BUTTON' && target.closest('[role="dialog"]')) return;
    e.preventDefault();
    e.stopPropagation();
    printNow();
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown, true));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown, true));
</script>
