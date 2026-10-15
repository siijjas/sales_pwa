<template>
  <BottomSheet :model-value="modelValue" title="Expense from the drawer" :subtitle="ctx?.opening_shift ? `Shift ${ctx.opening_shift}` : ''" @update:model-value="(v: boolean) => emit('update:modelValue', v)">
    <div class="space-y-4" @keydown.enter="onEnter">
      <p v-if="loading" class="text-[13px] text-muted">Loading…</p>
      <AppAlert v-else-if="loadError" tone="danger" :message="loadError" />

      <template v-else-if="ctx && !ctx.opening_shift">
        <AppAlert tone="warning" icon="clock" title="No open shift" message="Expenses come out of an open shift's cash drawer. Open your shift first." />
        <AppButton data-expense-primary block icon="play-circle" @click="go('shift-open')">Open shift</AppButton>
      </template>

      <AppAlert v-else-if="ctx && !ctx.allow_expense" tone="info" message="Your profile does not allow expenses. Ask your manager." />

      <template v-else-if="ctx">
        <div class="grid gap-3 sm:grid-cols-[10rem_minmax(0,1fr)]">
          <FormField label="Amount" required :hint="ctx.max_amount ? `Max ${currency} ${money(ctx.max_amount)}` : ''">
            <input
              ref="amountInput"
              v-model="amount"
              type="text"
              inputmode="decimal"
              autocomplete="off"
              placeholder="0.000"
              class="field-input tnum !min-h-[2.875rem] text-right text-[16px] font-bold"
              @focus="($event.target as HTMLInputElement).select()"
            />
          </FormField>
          <FormField label="Expense account" required>
            <BaseSelect v-model="account" placeholder="Select account">
              <option v-for="a in ctx.expense_accounts" :key="a.name" :value="a.name">{{ a.account_name }}</option>
            </BaseSelect>
          </FormField>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <FormField label="Paid to" hint="Optional">
            <BaseInput v-model="paidTo" placeholder="Shop, person or supplier" />
          </FormField>
          <FormField label="Remarks" :required="ctx.require_remarks" :hint="ctx.require_remarks ? 'Required on your profile' : 'Optional'">
            <BaseInput v-model="remarks" placeholder="What it was for" />
          </FormField>
        </div>
        <AppAlert v-if="error" tone="danger" :message="error" />
        <AppButton data-expense-primary size="lg" block icon="file-text" :loading="saving" :disabled="!valid" @click="submit">
          Record {{ currency }} {{ money(amountValue) }} <kbd class="ml-1 text-[11px] opacity-70">Enter</kbd>
        </AppButton>

        <div class="border-t border-line pt-3">
          <div class="mb-1.5 flex items-center justify-between text-[12.5px]">
            <span class="font-bold uppercase tracking-wide text-muted">This shift</span>
            <span class="tnum font-bold text-foreground">{{ currency }} {{ money(shiftTotal) }}</span>
          </div>
          <p v-if="!expenses.length" class="text-[13px] text-muted">No expenses yet.</p>
          <div v-for="m in expenses" :key="m.name" class="flex items-center justify-between gap-3 py-1 text-[13px]">
            <span class="min-w-0 truncate text-foreground">{{ accountName(m.expense_account) }}<span v-if="m.against_name || m.remarks" class="text-muted"> · {{ [m.against_name, m.remarks].filter(Boolean).join(' · ') }}</span></span>
            <span class="tnum shrink-0 font-semibold text-foreground">{{ currency }} {{ money(m.amount) }}</span>
          </div>
        </div>
      </template>
    </div>
  </BottomSheet>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../../api/frappe';
import type { CashMovementContext } from '../../types';
import { money } from '../../utils/format';
import { useToast } from '../../composables/useToast';
import { AppAlert, AppButton, BaseInput, BaseSelect, BottomSheet, FormField } from '../ui';

// The Counter's F6: an expense paid out of the open shift's drawer, without leaving
// the screen. Same endpoint and rules as the Shift area's Cash out screen.
const props = defineProps<{ modelValue: boolean; currency: string }>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'recorded'): void;
}>();

const router = useRouter();
const toast = useToast();
const ctx = ref<CashMovementContext | null>(null);
const loading = ref(false);
const loadError = ref('');
const error = ref('');
const saving = ref(false);
const amount = ref('');
const account = ref('');
const paidTo = ref('');
const remarks = ref('');
const amountInput = ref<HTMLInputElement | null>(null);

const amountValue = computed(() => Number(String(amount.value).replace(/[^0-9.]/g, '')) || 0);
const expenses = computed(() => (ctx.value?.movements || []).filter((m) => m.movement_type === 'Expense' && m.docstatus === 1));
const shiftTotal = computed(() => expenses.value.reduce((sum, m) => sum + m.amount, 0));
const valid = computed(() => {
  const c = ctx.value;
  if (!c || amountValue.value <= 0 || !account.value) return false;
  if (c.max_amount && amountValue.value > c.max_amount) return false;
  if (c.require_remarks && !remarks.value.trim()) return false;
  return true;
});
const accountName = (name: string | null) => ctx.value?.expense_accounts.find((a) => a.name === name)?.account_name || name || 'Expense';

async function load() {
  loading.value = true;
  loadError.value = '';
  try {
    ctx.value = await api.getCashMovementContext();
    const accounts = ctx.value.expense_accounts;
    if (!accounts.some((a) => a.name === account.value)) {
      account.value = (ctx.value.default_expense_account && accounts.some((a) => a.name === ctx.value!.default_expense_account) ? ctx.value.default_expense_account : accounts.length === 1 ? accounts[0].name : '') || '';
    }
  } catch (e: any) {
    loadError.value = e?.message || 'Could not load the expense accounts';
  } finally {
    loading.value = false;
    focusFirst();
  }
}

function focusFirst() {
  nextTick(() =>
    window.setTimeout(() => {
      (document.activeElement as HTMLElement | null)?.blur?.();
      if (amountInput.value) amountInput.value.focus();
      else (document.querySelector('[role="dialog"] [data-expense-primary]') as HTMLElement | null)?.focus();
    }, 60),
  );
}

function onEnter(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName;
  if (tag === 'BUTTON' || tag === 'SELECT') return;
  e.preventDefault();
  if (valid.value) submit();
}

async function submit() {
  if (!valid.value || saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    const m = await api.createCashMovement({
      movement_type: 'Expense',
      amount: amountValue.value,
      expense_account: account.value,
      against_name: paidTo.value.trim() || undefined,
      remarks: remarks.value.trim() || undefined,
    });
    toast.success(`Expense ${props.currency} ${money(m.amount)} recorded`, { message: `${accountName(m.expense_account)} · ${m.name}` });
    amount.value = '';
    paidTo.value = '';
    remarks.value = '';
    ctx.value = ctx.value ? { ...ctx.value, movements: [m, ...ctx.value.movements] } : ctx.value;
    emit('recorded');
    emit('update:modelValue', false);
  } catch (e: any) {
    error.value = e?.message || 'Could not record the expense';
  } finally {
    saving.value = false;
  }
}

function go(name: string) {
  emit('update:modelValue', false);
  router.push({ name, query: { back: router.currentRoute.value.name as string } });
}

// Esc closes the sheet wherever the focus is (it may still be on the screen behind while loading).
function onWindowKeydown(e: KeyboardEvent) {
  if (props.modelValue && e.key === 'Escape') {
    e.preventDefault();
    emit('update:modelValue', false);
  }
}
// Capture phase: a box behind the sheet that still has focus would stop Esc for itself.
onMounted(() => window.addEventListener('keydown', onWindowKeydown, true));
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKeydown, true));

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      // Nothing behind the sheet may keep the keyboard (an open customer list would take Enter and Esc).
      (document.activeElement as HTMLElement | null)?.blur?.();
      error.value = '';
      load();
    }
  },
);
</script>
