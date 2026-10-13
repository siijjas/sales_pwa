<template>
  <WorkspacePage :back="{ name: 'shift' }" title="Cash out" :subtitle="ctx?.opening_shift ? `Shift ${ctx.opening_shift}` : 'Expenses and deposits'">
    <SkeletonList v-if="loading" :rows="3" height="6rem" />

    <AppAlert v-else-if="loadError" tone="danger" :message="loadError" />

    <AppCard v-else-if="ctx && !ctx.opening_shift" padding="lg">
      <div class="flex items-start gap-3.5">
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-warning/16 text-warning"><AppIcon name="clock" :size="22" /></span>
        <div class="min-w-0 flex-1">
          <p class="text-[15px] font-bold text-foreground">No open shift</p>
          <p class="mt-0.5 text-[13px] leading-relaxed text-muted">Expenses and deposits come out of an open shift's cash drawer. Open your shift first.</p>
          <AppButton class="mt-3" size="sm" icon="play-circle" @click="router.push({ name: 'shift-open' })">Open shift</AppButton>
        </div>
      </div>
    </AppCard>

    <div v-else-if="ctx" class="space-y-5 pb-28">
      <!-- Form -->
      <AppCard padding="lg" class="space-y-4">
        <AppAlert v-if="!typeOptions.length" tone="info" message="Your profile allows neither expenses nor deposits. Ask your manager." />

        <template v-else>
          <SegmentedControl v-if="typeOptions.length > 1" :model-value="form.movement_type" :options="typeOptions" @update:modelValue="setType" />

          <FormField label="Amount" required :hint="ctx.max_amount ? `Max ${currency} ${money(ctx.max_amount)} per entry.` : ''">
            <BaseInput v-model="form.amount" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" min="0" step="0.01" />
          </FormField>

          <FormField v-if="isExpense" label="Expense account" required>
            <BaseSelect v-model="form.expense_account" placeholder="Select account">
              <option v-for="a in ctx.expense_accounts" :key="a.name" :value="a.name">{{ a.account_name }}</option>
            </BaseSelect>
          </FormField>

          <FormField :label="isExpense ? 'Paid to' : 'Deposited with'" :hint="isExpense ? 'Optional — e.g. Shell Station 42' : 'Optional — who received the cash'">
            <BaseInput v-model="form.against_name" :placeholder="isExpense ? 'Supplier or place' : 'Cashier or office'" />
          </FormField>

          <FormField label="Remarks" :required="ctx.require_remarks" :hint="ctx.require_remarks ? 'Required on your profile.' : 'Optional'">
            <BaseTextarea v-model="form.remarks" :rows="2" placeholder="Add a note…" />
          </FormField>

          <p class="rounded-xl bg-card-muted px-3 py-2 text-xs text-muted">
            <span class="font-semibold text-foreground">{{ ctx.cash_account || 'Cash drawer' }}</span>
            →
            <span class="font-semibold text-foreground">{{ isExpense ? (form.expense_account || 'expense account') : (ctx.back_office_cash_account || 'back office cash') }}</span>
          </p>

          <AppAlert v-if="error" tone="danger" :message="error" />
        </template>
      </AppCard>

      <!-- This shift -->
      <section>
        <SectionHeader title="This shift" />
        <div class="grid grid-cols-2 gap-2.5">
          <KpiTile label="Expenses" :value="money(totals.expenses)" :sub="plural(counts.expenses, 'entry', 'entries')" icon="file-text" tone="warning" />
          <KpiTile label="Deposited" :value="money(totals.deposits)" :sub="plural(counts.deposits, 'entry', 'entries')" icon="banknote" tone="info" />
        </div>
      </section>

      <section>
        <SectionHeader title="Movements" />
        <EmptyState v-if="!ctx.movements.length" icon="file-text" title="Nothing yet" description="Expenses and deposits on this shift will appear here." />
        <div v-else class="space-y-2.5">
          <AppCard v-for="m in ctx.movements" :key="m.name" padding="sm">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <StatusBadge :tone="m.movement_type === 'Expense' ? 'warning' : 'info'" :dot="false">{{ m.movement_type }}</StatusBadge>
                  <p class="truncate text-sm font-semibold text-foreground">{{ accountLabel(m) }}</p>
                </div>
                <p class="mt-1 text-xs text-muted">{{ m.name }}<span v-if="m.journal_entry"> · {{ m.journal_entry }}</span></p>
                <p v-if="m.against_name" class="mt-0.5 text-xs text-muted">{{ m.movement_type === 'Expense' ? 'Paid to' : 'Deposited with' }} {{ m.against_name }}</p>
              </div>
              <p class="tnum shrink-0 font-bold text-foreground">{{ currency }} {{ money(m.amount) }}</p>
            </div>
            <p v-if="m.remarks" class="mt-3 rounded-xl bg-card-muted p-2.5 text-sm text-muted">{{ m.remarks }}</p>
            <div v-if="store.isManager || (store.capabilities.can_cancel_cash_movement && m.driver === store.session?.user)" class="mt-3 flex justify-end">
              <AppButton variant="ghost" size="sm" icon="x" :loading="cancelling === m.name" @click="cancel(m)">Cancel entry</AppButton>
            </div>
          </AppCard>
        </div>
      </section>
    </div>

    <StickyBar v-if="ctx?.opening_shift && typeOptions.length">
      <AppButton size="lg" block :icon="isExpense ? 'file-text' : 'banknote'" :disabled="!isValid" :loading="submitting" @click="submit">
        {{ submitting ? 'Posting…' : isExpense ? 'Record expense' : 'Record deposit' }}
      </AppButton>
    </StickyBar>

    <!-- After a deposit: the drawer has been handed in, so this is the natural moment to close. -->
    <BottomSheet v-model="closePromptOpen" title="Deposit recorded" size="sm">
      <div class="space-y-4">
        <p class="text-sm text-muted">
          <span class="tnum font-semibold text-foreground">{{ currency }} {{ money(lastDeposit?.amount) }}</span> deposited to the office on shift
          <span class="font-semibold text-foreground">{{ ctx?.opening_shift }}</span>.
          <template v-if="canCloseShift">Done for the day? Close your shift now to count the drawer against what is expected.</template>
          <template v-else>Only a manager can close this shift. Let them know the cash has been handed in.</template>
        </p>
        <div class="grid gap-2" :class="canCloseShift ? 'grid-cols-2' : ''">
          <AppButton variant="secondary" size="lg" block @click="closePromptOpen = false">{{ canCloseShift ? 'Not yet' : 'OK' }}</AppButton>
          <AppButton v-if="canCloseShift" size="lg" block icon="check" @click="goCloseShift">Close shift</AppButton>
        </div>
      </div>
    </BottomSheet>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import * as api from '../api/frappe';
import { useSessionStore } from '../stores/session';
import { useToast } from '../composables/useToast';
import { useConfirm } from '../composables/useConfirm';
import { money, plural } from '../utils/format';
import type { CashMovement, CashMovementContext, CashMovementType } from '../types';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, BottomSheet, FormField, BaseInput, BaseSelect, BaseTextarea, SkeletonList, EmptyState, KpiTile, SectionHeader, StatusBadge, SegmentedControl, StickyBar } from '../components/ui';

const store = useSessionStore();
const router = useRouter();
const toast = useToast();
const { confirm } = useConfirm();
const currency = computed(() => store.currencyDisplay);

// Prompt to close the shift once cash has been deposited to the office.
const closePromptOpen = ref(false);
const lastDeposit = ref<CashMovement | null>(null);
const canCloseShift = computed(() => store.isManager || store.capabilities.can_close_shift);
const goCloseShift = () => {
  closePromptOpen.value = false;
  router.push({ name: 'shift-close' });
};

const ctx = ref<CashMovementContext | null>(null);
const loading = ref(true);
const loadError = ref('');
const submitting = ref(false);
const cancelling = ref('');
const error = ref('');

const form = ref<{ movement_type: CashMovementType; amount: number | string | null; expense_account: string; against_name: string; remarks: string }>({
  movement_type: 'Expense',
  amount: null,
  expense_account: '',
  against_name: '',
  remarks: '',
});

const typeOptions = computed(() => {
  const list: { value: CashMovementType; label: string }[] = [];
  if (ctx.value?.allow_expense) list.push({ value: 'Expense', label: 'Expense' });
  if (ctx.value?.allow_cash_deposit) list.push({ value: 'Deposit', label: 'Deposit to office' });
  return list;
});
const isExpense = computed(() => form.value.movement_type === 'Expense');

const amountNumber = computed(() => Number(form.value.amount) || 0);
const isValid = computed(() => {
  if (!ctx.value || amountNumber.value <= 0) return false;
  if (ctx.value.max_amount && amountNumber.value > ctx.value.max_amount) return false;
  if (isExpense.value && !form.value.expense_account) return false;
  if (ctx.value.require_remarks && !form.value.remarks.trim()) return false;
  return true;
});

const totals = computed(() => sum((m) => m.amount));
const counts = computed(() => sum(() => 1));
function sum(pick: (m: CashMovement) => number) {
  const out = { expenses: 0, deposits: 0 };
  for (const m of ctx.value?.movements || []) {
    if (m.movement_type === 'Expense') out.expenses += pick(m);
    else out.deposits += pick(m);
  }
  return out;
}

const accountLabel = (m: CashMovement) => {
  const name = m.target_account || '';
  const account = ctx.value?.expense_accounts.find((a) => a.name === name);
  return account?.account_name || name;
};

function setType(value: string) {
  form.value.movement_type = value as CashMovementType;
  error.value = '';
}

const load = async () => {
  loading.value = true;
  loadError.value = '';
  try {
    ctx.value = await api.getCashMovementContext();
    if (!ctx.value.allow_expense && ctx.value.allow_cash_deposit) form.value.movement_type = 'Deposit';
    if (!form.value.expense_account && ctx.value.default_expense_account) form.value.expense_account = ctx.value.default_expense_account;
  } catch (e: any) {
    loadError.value = e?.message || 'Failed to load cash movements.';
  } finally {
    loading.value = false;
  }
};

const submit = async () => {
  if (!isValid.value) return;
  submitting.value = true;
  error.value = '';
  try {
    const created = await api.createCashMovement({
      movement_type: form.value.movement_type,
      amount: amountNumber.value,
      expense_account: isExpense.value ? form.value.expense_account : undefined,
      against_name: form.value.against_name,
      remarks: form.value.remarks,
    });
    ctx.value!.movements.unshift(created);
    toast.success(`${created.movement_type} recorded`, { message: `${created.name}${created.journal_entry ? ` · ${created.journal_entry}` : ''}` });
    form.value = { ...form.value, amount: null, against_name: '', remarks: '' };
    if (created.movement_type === 'Deposit') {
      lastDeposit.value = created;
      closePromptOpen.value = true;
    }
  } catch (e: any) {
    error.value = e?.message || 'Failed to record the cash movement.';
  } finally {
    submitting.value = false;
  }
};

const cancel = async (m: CashMovement) => {
  const ok = await confirm({
    title: `Cancel this ${m.movement_type.toLowerCase()}?`,
    message: `${m.name} for ${currency.value} ${money(m.amount)} is cancelled and its Journal Entry reversed.`,
    confirmLabel: 'Cancel entry',
    cancelLabel: 'Keep',
    tone: 'danger',
    icon: 'trash',
  });
  if (!ok) return;
  cancelling.value = m.name;
  error.value = '';
  try {
    await api.cancelCashMovement(m.name);
    ctx.value!.movements = ctx.value!.movements.filter((x) => x.name !== m.name);
    toast.success('Entry cancelled');
  } catch (e: any) {
    error.value = e?.message || 'Failed to cancel.';
  } finally {
    cancelling.value = '';
  }
};

onMounted(load);
</script>
