<template>
  <WorkspacePage back eyebrow="Manager · invoicing" title="Invoice options" description="Named ways of raising an invoice: a numbering series plus a tax template. Enable them per Sales Profile." width="wide">
    <template #actions>
      <AppButton variant="secondary" size="sm" icon="plus" @click="startNew">New</AppButton>
    </template>

    <div class="grid gap-5 lg:grid-cols-[320px,1fr]">
      <!-- List -->
      <aside class="space-y-3" :class="selected ? 'hidden lg:block' : ''">
        <SkeletonList v-if="loading" :rows="3" height="4.5rem" />
        <div v-else class="space-y-2">
          <AppCard
            v-for="opt in options"
            :key="opt.name"
            padding="sm"
            interactive
            :class="selected?.name === opt.name ? 'ring-2 ring-primary' : ''"
            @click="select(opt)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-bold text-foreground">{{ opt.option_name }}</span>
              <StatusBadge :tone="opt.disabled ? 'neutral' : 'success'" :dot="false">{{ opt.disabled ? 'Disabled' : 'Active' }}</StatusBadge>
            </div>
            <p class="mt-1 truncate text-sm text-muted">{{ opt.naming_series }}</p>
            <p class="mt-1 truncate text-xs text-subtle">{{ opt.taxes_and_charges || 'No tax' }}<span v-if="opt.company"> · {{ opt.company }}</span></p>
            <p class="mt-1 truncate text-xs text-subtle">{{ paymentRuleLabel(opt) }}</p>
          </AppCard>
          <AppButton variant="secondary" block icon="plus" @click="startNew">Create option</AppButton>
          <EmptyState v-if="!options.length" icon="file-text" title="No invoice options" description="Create one, then enable it on a Sales Profile." />
        </div>
      </aside>

      <!-- Editor -->
      <div v-if="!selected" class="hidden lg:flex">
        <EmptyState class="w-full" icon="sliders" title="Nothing selected" description="Pick an option or create a new one." />
      </div>

      <div v-else class="space-y-4 pb-28">
        <button class="flex items-center gap-1 text-sm font-semibold text-primary lg:hidden" @click="selected = null">
          <AppIcon name="chevron-left" :size="16" /> Options
        </button>

        <AppAlert v-if="errorMsg" tone="danger" title="Couldn't save option" :message="errorMsg" />
        <AppAlert v-if="notice" tone="success" :message="notice" />

        <AppCard>
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Option name" required hint="What staff see when they pick it, e.g. VAT invoice, Export invoice.">
              <BaseInput v-model="form.option_name" placeholder="e.g. VAT invoice" />
            </FormField>
            <FormField label="Company" hint="Optional. Limits the tax template choice below.">
              <BaseSelect v-model="form.company" placeholder="Any company">
                <option v-for="c in choices.companies" :key="c.name" :value="c.name">{{ c.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Invoice numbering series" required hint="From the Sales Invoice naming series list (Desk → Settings → Naming Series).">
              <BaseSelect v-model="form.naming_series" placeholder="Select series">
                <option v-for="s in choices.naming_series" :key="s" :value="s">{{ s }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Taxes & charges template" hint="Leave empty to raise the invoice without taxes.">
              <BaseSelect v-model="form.taxes_and_charges" placeholder="No tax">
                <option v-for="t in filteredTemplates" :key="t.name" :value="t.name">{{ t.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Description" hint="Shown under the option when staff choose it." class="md:col-span-2">
              <BaseTextarea v-model="form.description" :rows="2" placeholder="Optional" />
            </FormField>
          </div>
          <label class="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl border border-line bg-card-muted px-3.5 py-3">
            <input type="checkbox" v-model="form.disabled" class="h-4 w-4 accent-primary" />
            <span class="text-sm font-medium text-foreground">Disabled (hidden from staff, kept on profiles)</span>
          </label>
        </AppCard>

        <!-- Payment rule -->
        <AppCard>
          <div class="flex items-center gap-2.5">
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/12 text-primary"><AppIcon name="wallet" :size="16" /></span>
            <h3 class="text-sm font-bold text-foreground">Payment rule</h3>
          </div>
          <p class="mt-2 text-xs text-muted">Staff only see this option when it fits the payment they chose for the invoice.</p>
          <label class="mt-4 flex cursor-pointer items-center gap-3 rounded-2xl border border-line bg-card-muted px-3.5 py-3">
            <input type="checkbox" v-model="form.available_for_credit" class="h-4 w-4 accent-primary" />
            <span class="text-sm font-medium text-foreground">Available for credit (pay later) invoices</span>
          </label>
          <div class="mt-4 flex items-center justify-between gap-3">
            <p class="text-xs font-bold uppercase tracking-wider text-muted">Paid-now modes of payment <span class="font-medium normal-case tracking-normal">· empty = every mode</span></p>
            <span class="rounded-full bg-card-muted px-2.5 py-1 text-xs font-bold text-muted">{{ form.payment_modes?.length || 0 }}</span>
          </div>
          <div class="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <label
              v-for="mode in choices.payment_modes"
              :key="mode.name"
              class="flex cursor-pointer items-center gap-3 rounded-2xl border p-3 transition"
              :class="(form.payment_modes || []).includes(mode.name) ? 'border-success/40 bg-success/[0.06]' : 'border-line hover:bg-card-muted'"
            >
              <input type="checkbox" :value="mode.name" v-model="form.payment_modes" class="h-4 w-4 accent-primary" />
              <span class="min-w-0">
                <span class="block truncate text-sm font-semibold text-foreground">{{ mode.name }}</span>
                <span class="block text-xs text-muted">{{ mode.type }}</span>
              </span>
            </label>
          </div>
        </AppCard>

        <AppButton v-if="selected.name" variant="danger" size="sm" icon="trash" :loading="deleting" @click="remove">Delete option</AppButton>
      </div>
    </div>

    <StickyBar v-if="selected">
      <AppButton size="lg" block icon="save" :disabled="!isValid" :loading="saving" @click="save">
        {{ saving ? 'Saving…' : selected.name ? 'Update option' : 'Save option' }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { listAllInvoiceOptions, getInvoiceOptionChoices, saveInvoiceOption, deleteInvoiceOption } from '../api/frappe';
import type { InvoiceOption, InvoiceOptionChoices } from '../types';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, FormField, BaseInput, BaseSelect, BaseTextarea, StatusBadge, SkeletonList, EmptyState, StickyBar } from '../components/ui';

const loading = ref(true);
const saving = ref(false);
const deleting = ref(false);
const errorMsg = ref('');
const notice = ref('');
const options = ref<InvoiceOption[]>([]);
const choices = ref<InvoiceOptionChoices>({ naming_series: [], tax_templates: [], companies: [], payment_modes: [] });

function paymentRuleLabel(opt: InvoiceOption): string {
  const paid = opt.payment_modes?.length ? `paid by ${opt.payment_modes.join(', ')}` : 'any paid-now mode';
  return opt.available_for_credit === false ? `Paid now only: ${paid}` : `Credit · ${paid}`;
}
const selected = ref<InvoiceOption | Partial<InvoiceOption> | null>(null);

const blank = (): Partial<InvoiceOption> => ({
  option_name: '',
  naming_series: '',
  taxes_and_charges: '',
  company: '',
  description: '',
  disabled: false,
  available_for_credit: true,
  payment_modes: [],
});
const form = ref<Partial<InvoiceOption>>(blank());

const filteredTemplates = computed(() =>
  form.value.company ? choices.value.tax_templates.filter((t) => t.company === form.value.company) : choices.value.tax_templates,
);
const isValid = computed(() => !!form.value.option_name?.trim() && !!form.value.naming_series);

function startNew() {
  selected.value = blank();
  form.value = blank();
  errorMsg.value = '';
  notice.value = '';
}
function select(opt: InvoiceOption) {
  selected.value = opt;
  form.value = {
    ...opt,
    taxes_and_charges: opt.taxes_and_charges || '',
    company: opt.company || '',
    description: opt.description || '',
    available_for_credit: opt.available_for_credit !== false,
    payment_modes: [...(opt.payment_modes || [])],
  };
  errorMsg.value = '';
  notice.value = '';
}

async function load() {
  loading.value = true;
  try {
    const [opts, ch] = await Promise.all([listAllInvoiceOptions(), getInvoiceOptionChoices()]);
    options.value = opts;
    choices.value = ch;
    if (opts.length && !selected.value) select(opts[0]);
  } catch (e: any) {
    errorMsg.value = e?.message || 'Failed to load invoice options';
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!isValid.value) return;
  saving.value = true;
  errorMsg.value = '';
  notice.value = '';
  try {
    const saved = await saveInvoiceOption({ ...form.value, name: selected.value?.name });
    const idx = options.value.findIndex((o) => o.name === saved.name);
    if (idx >= 0) options.value[idx] = saved;
    else options.value.push(saved);
    select(saved);
    notice.value = `Saved ${saved.option_name}. Enable it on a Sales Profile to let staff use it.`;
  } catch (e: any) {
    errorMsg.value = e?.message || 'Failed to save option';
  } finally {
    saving.value = false;
  }
}

async function remove() {
  const name = selected.value?.name;
  if (!name || !confirm(`Delete invoice option "${name}"?`)) return;
  deleting.value = true;
  errorMsg.value = '';
  try {
    await deleteInvoiceOption(name);
    options.value = options.value.filter((o) => o.name !== name);
    selected.value = null;
  } catch (e: any) {
    errorMsg.value = e?.message || 'Failed to delete option';
  } finally {
    deleting.value = false;
  }
}

onMounted(load);
</script>
