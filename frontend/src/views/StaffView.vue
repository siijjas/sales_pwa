<template>
  <WorkspacePage eyebrow="Manager" title="Staff" subtitle="Sales profiles for van drivers and field sales staff" width="wide">
    <template #actions>
      <AppButton size="sm" icon="plus" @click="startNew">New profile</AppButton>
    </template>

    <div class="grid gap-5 lg:grid-cols-[320px,1fr]">
      <!-- List -->
      <aside class="space-y-3" :class="selectedProfile ? 'hidden lg:block' : ''">
        <SearchBar v-model="searchQuery" placeholder="Search profiles…" />
        <SkeletonList v-if="loading" :rows="4" height="4.5rem" />
        <div v-else class="space-y-2">
          <AppCard
            v-for="p in filteredProfiles"
            :key="p.name"
            padding="sm"
            interactive
            :class="selectedProfile?.name === p.name ? 'ring-2 ring-primary' : ''"
            @click="selectProfile(p)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-bold text-foreground">{{ p.profile_name }}</span>
              <StatusBadge :tone="p.is_active ? 'success' : 'neutral'" :dot="false">{{ p.is_active ? 'Active' : 'Draft' }}</StatusBadge>
            </div>
            <p class="mt-1 truncate text-sm text-muted">{{ p.company }}</p>
            <p class="mt-1 text-xs text-subtle">
              <span class="font-semibold" :class="p.profile_type === 'Field Sales' ? 'text-info' : 'text-primary'">{{ p.profile_type || 'Van Sales' }}</span>
              · {{ p.assigned_drivers?.length || 0 }} staff
            </p>
          </AppCard>
          <EmptyState v-if="!filteredProfiles.length" icon="user" title="No profiles" description="Create your first sales profile.">
            <template #action><AppButton variant="secondary" icon="plus" @click="startNew">Create profile</AppButton></template>
          </EmptyState>
        </div>
      </aside>

      <!-- Editor -->
      <div v-if="!selectedProfile" class="hidden lg:flex">
        <EmptyState class="w-full" icon="sliders" title="Nothing selected" description="Pick a profile or create a new one." />
      </div>

      <div v-else class="space-y-4 pb-28">
        <div class="flex items-center justify-between gap-3">
          <button class="flex items-center gap-1 text-sm font-semibold text-primary lg:hidden" @click="selectedProfile = null">
            <AppIcon name="chevron-left" :size="16" /> All profiles
          </button>
          <p class="hidden truncate text-sm font-bold text-foreground lg:block">{{ selectedProfile.name ? form.profile_name : 'New profile' }}</p>
          <AppButton v-if="selectedProfile.name" variant="ghost" size="sm" icon="trash" class="text-danger" :loading="isDeleting" @click="removeProfile">Delete</AppButton>
        </div>

        <AppAlert v-if="errorMsg" tone="danger" title="Couldn't save profile" :message="errorMsg" />

        <!-- Identity -->
        <FormSection title="Identity & core" icon="user">
          <FormField label="Profile type" required :hint="isFieldSales ? 'Staff take orders and collect payments. Invoicing, delivery and returns stay in the back office.' : 'Staff load a van, sell and deliver from it, take returns and reconcile cash at shift close.'">
            <SegmentedControl
              :model-value="form.profile_type || 'Van Sales'"
              :options="[{ value: 'Van Sales', label: 'Van Sales' }, { value: 'Field Sales', label: 'Field Sales' }]"
              @update:modelValue="setProfileType"
            />
          </FormField>
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Profile name" required>
              <BaseInput :model-value="form.profile_name ?? ''" :placeholder="isFieldSales ? 'e.g. North Region Field Team' : 'e.g. Riyadh Van Fleet'" @update:model-value="(v) => (form.profile_name = String(v))" />
            </FormField>
            <FormField label="Company" required>
              <BaseSelect :model-value="form.company ?? ''" @update:model-value="(v) => (form.company = v)" placeholder="Select company">
                <option v-for="c in options.companies" :key="c.name" :value="c.name">{{ c.name }}</option>
              </BaseSelect>
            </FormField>
          </div>
          <ToggleSwitch :model-value="!!form.is_active" label="Profile is active" hint="Inactive profiles keep their settings; staff on them cannot use the app." @update:model-value="(v: boolean) => (form.is_active = v)" />
        </FormSection>

        <!-- Warehouses -->
        <FormSection :title="isFieldSales ? 'Stock display & routing' : 'Warehouses & routing'" icon="boxes">
          <ToggleSwitch
            v-if="!isFieldSales" :model-value="!!form.separate_van_warehouse"
            label="Van has its own warehouse (stock is loaded into it from the main warehouse)"
            class="mb-4" @update:model-value="(v: boolean) => (form.separate_van_warehouse = v)"
          />
          <p v-if="!isFieldSales && !form.separate_van_warehouse" class="mb-4 text-xs text-muted">
            This van sells straight from the main warehouse: orders, invoices, returns and the stock dashboard use it, and stock loading is hidden.
          </p>
          <div class="grid gap-4 md:grid-cols-2">
            <template v-if="!isFieldSales">
              <FormField :label="form.separate_van_warehouse ? 'Main warehouse' : 'Main (selling) warehouse'" required>
                <BaseSelect :model-value="form.source_warehouse ?? ''" @update:model-value="(v) => (form.source_warehouse = v)" placeholder="Select main warehouse">
                  <option v-for="w in filteredWarehouses" :key="w.name" :value="w.name">{{ w.name }}</option>
                </BaseSelect>
              </FormField>
              <FormField v-if="form.separate_van_warehouse" label="Van warehouse" required>
                <BaseSelect :model-value="form.van_warehouse ?? ''" @update:model-value="(v) => (form.van_warehouse = v)" placeholder="Select van warehouse">
                  <option v-for="w in filteredWarehouses" :key="w.name" :value="w.name">{{ w.name }}</option>
                </BaseSelect>
              </FormField>
            </template>
            <FormField v-else label="Stock warehouse (display only)" hint="Catalog shows available qty from here for information. It never blocks an order.">
              <BaseSelect :model-value="form.stock_warehouse ?? ''" @update:model-value="(v) => (form.stock_warehouse = v)" placeholder="Company default warehouse">
                <option v-for="w in filteredWarehouses" :key="w.name" :value="w.name">{{ w.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Delivery route (territory)">
              <BaseSelect :model-value="form.delivery_route ?? ''" @update:model-value="(v) => (form.delivery_route = v)" placeholder="Optional route restriction">
                <option v-for="r in options.routes" :key="r.name" :value="r.name">{{ r.name }}</option>
              </BaseSelect>
            </FormField>
          </div>
        </FormSection>

        <!-- Customer access -->
        <FormSection title="Customer access" icon="users" :badge="`${form.allowed_customer_groups?.length || 0}`">
          <p class="text-xs text-muted">Restrict staff on this profile to customers in these groups. Leave empty to allow all groups (still subject to the delivery route above, if set).</p>
          <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <label
              v-for="group in options.customer_groups"
              :key="group.name"
              class="flex cursor-pointer items-center gap-3 rounded-2xl border p-3 transition"
              :class="(form.allowed_customer_groups || []).includes(group.name) ? 'border-success/40 bg-success/[0.06]' : 'border-line hover:bg-card-muted'"
            >
              <input type="checkbox" :value="group.name" v-model="form.allowed_customer_groups" class="h-4 w-4 accent-primary" />
              <span class="text-sm font-semibold text-foreground">{{ group.name }}</span>
            </label>
          </div>
        </FormSection>

        <!-- Drivers -->
        <FormSection :title="isFieldSales ? 'Assigned sales staff' : 'Assigned drivers'" icon="users" :badge="`${form.assigned_drivers?.length || 0}`">
          <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <label
              v-for="user in options.users"
              :key="user.name"
              class="flex cursor-pointer items-start gap-3 rounded-2xl border p-3 transition"
              :class="isDriverAssigned(user.name) ? 'border-primary/40 bg-primary/[0.06]' : 'border-line hover:bg-card-muted'"
            >
              <input type="checkbox" class="mt-0.5 h-4 w-4 accent-primary" :checked="isDriverAssigned(user.name)" @change="toggleDriver(user.name)" />
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-foreground">{{ user.full_name }}</p>
                <p class="truncate text-xs text-muted">{{ user.name }}</p>
              </div>
            </label>
          </div>
        </FormSection>

        <!-- Controls -->
        <FormSection title="Operational controls" icon="sliders">
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Daily credit limit" hint="Max credit sales per day.">
              <BaseInput :model-value="form.daily_credit_limit ?? 0" @update:model-value="(v) => (form.daily_credit_limit = Number(v) || 0)" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" />
            </FormField>
            <FormField v-if="!isFieldSales" label="Low stock threshold" hint="Alert when van stock drops below this.">
              <BaseInput :model-value="form.low_stock_threshold ?? 0" @update:model-value="(v) => (form.low_stock_threshold = Number(v) || 0)" type="number" inputmode="numeric" />
            </FormField>
          </div>
          <div class="grid gap-2 md:grid-cols-2 [&>label]:rounded-2xl [&>label]:bg-card-muted [&>label]:px-3.5 [&>label]:py-2">
            <ToggleSwitch :model-value="!!form.allow_rate_change" label="Allow modifying item rates" @update:model-value="(v: boolean) => (form.allow_rate_change = v)" />
            <ToggleSwitch :model-value="!!form.allow_discount_change" label="Allow modifying discounts" @update:model-value="(v: boolean) => (form.allow_discount_change = v)" />
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.allow_sale_without_stock" label="Allow selling items not in stock" @update:model-value="(v: boolean) => (form.allow_sale_without_stock = v)" />
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.hide_unavailable_items" label="Hide items not in stock from the catalog" @update:model-value="(v: boolean) => (form.hide_unavailable_items = v)" />
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.allow_credit_sale" label="Allow credit sales (invoice now, collect later)" @update:model-value="(v: boolean) => (form.allow_credit_sale = v)" />
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.allow_return" label="Allow returns" @update:model-value="(v: boolean) => (form.allow_return = v)" />
            <ToggleSwitch :model-value="!!form.show_customer_balance" label="Show customer balance and ledger" @update:model-value="(v: boolean) => (form.show_customer_balance = v)" />
            <ToggleSwitch :model-value="!!form.allow_create_customer" label="Allow creating new customers" @update:model-value="(v: boolean) => (form.allow_create_customer = v)" />
            <ToggleSwitch v-if="form.allow_create_customer" :model-value="!!form.allow_duplicate_customer_names" label="Allow duplicate customer names" @update:model-value="(v: boolean) => (form.allow_duplicate_customer_names = v)" />
            <ToggleSwitch :model-value="!!form.use_shifts" label="Use shifts (opening float, cash reconciliation at close)" @update:model-value="(v: boolean) => (form.use_shifts = v)" />
            <ToggleSwitch v-if="form.use_shifts" :model-value="!!form.require_open_shift" label="Require an open shift to sell, collect or log expenses" @update:model-value="(v: boolean) => (form.require_open_shift = v)" />
            <ToggleSwitch v-if="form.use_shifts" :model-value="!!form.allow_driver_close_shift" label="Staff can close their own shift (off: managers only)" @update:model-value="(v: boolean) => (form.allow_driver_close_shift = v)" />
            <ToggleSwitch v-if="form.use_shifts" :model-value="!!form.hide_expected_amount" label="Blind cash count (hide expected amounts at close)" @update:model-value="(v: boolean) => (form.hide_expected_amount = v)" />
          </div>
          <div v-if="!isFieldSales && form.allow_return" class="grid gap-4 md:grid-cols-2">
            <FormField label="Return validity (days)" hint="Items can only be returned if the customer bought them within this many days. 0 = no limit.">
              <BaseInput :model-value="form.return_validity_days ?? 0" @update:model-value="(v) => (form.return_validity_days = Number(v) || 0)" type="number" inputmode="numeric" placeholder="0" />
            </FormField>
          </div>
          <div v-if="form.use_shifts" class="grid gap-4 md:grid-cols-2">
            <FormField label="Variance tolerance" hint="A closing whose counted cash is off by more than this is flagged for you. 0 flags any difference. Never blocks closing.">
              <BaseInput :model-value="form.variance_tolerance ?? 0" @update:model-value="(v) => (form.variance_tolerance = Number(v) || 0)" type="number" inputmode="decimal" :prefix="currency" placeholder="0.00" />
            </FormField>
          </div>
          <div class="grid gap-2 md:grid-cols-2 [&>label]:rounded-2xl [&>label]:bg-card-muted [&>label]:px-3.5 [&>label]:py-2">
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.validate_stock_on_save" label="Strictly validate stock on save" @update:model-value="(v: boolean) => (form.validate_stock_on_save = v)" />
            <ToggleSwitch v-if="!isFieldSales" :model-value="!!form.allow_offline_stock_dashboard" label="Enable offline stock dashboard" @update:model-value="(v: boolean) => (form.allow_offline_stock_dashboard = v)" />
            <ToggleSwitch :model-value="!!form.ignore_pricing_rule" label="Ignore active pricing rules" @update:model-value="(v: boolean) => (form.ignore_pricing_rule = v)" />
          </div>
        </FormSection>

        <!-- Pricing & tax -->
        <FormSection title="Pricing & tax" icon="receipt">
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Selling price list">
              <BaseSelect :model-value="form.selling_price_list ?? ''" @update:model-value="(v) => (form.selling_price_list = v)" placeholder="Default from selling settings">
                <option v-for="p in options.price_lists" :key="p.name" :value="p.name">{{ p.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Currency">
              <BaseSelect :model-value="form.currency ?? ''" @update:model-value="(v) => (form.currency = v)" placeholder="Company default">
                <option v-for="c in options.currencies" :key="c.name" :value="c.name">{{ c.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Taxes & charges template">
              <BaseSelect :model-value="form.taxes_and_charges ?? ''" @update:model-value="(v) => (form.taxes_and_charges = v)" placeholder="None (calculate dynamically)">
                <option v-for="t in filteredTaxTemplates" :key="t.name" :value="t.name">{{ t.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Apply discount on">
              <BaseSelect :model-value="form.apply_discount_on ?? ''" @update:model-value="(v) => (form.apply_discount_on = v)">
                <option value="Grand Total">Grand Total</option>
                <option value="Net Total">Net Total</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="form.allow_discount_change" label="Max discount %" hint="Largest order discount staff may give. 0 = no cap.">
              <BaseInput :model-value="form.max_discount_percent ?? 0" @update:model-value="(v) => (form.max_discount_percent = Number(v) || 0)" type="number" inputmode="decimal" min="0" max="100" placeholder="0" />
            </FormField>
          </div>
          <div class="grid gap-2 md:grid-cols-2 [&>label]:rounded-2xl [&>label]:bg-card-muted [&>label]:px-3.5 [&>label]:py-2">
            <ToggleSwitch :model-value="!!form.use_customer_price_list" label="Use the customer's own price list when they have one" @update:model-value="(v: boolean) => (form.use_customer_price_list = v)" />
            <ToggleSwitch :model-value="!!form.allow_zero_rated_items" label="Allow zero rated items (lines priced at 0)" @update:model-value="(v: boolean) => (form.allow_zero_rated_items = v)" />
          </div>
        </FormSection>

        <!-- Invoice options -->
        <FormSection v-if="!isFieldSales" title="Invoice options" icon="file-text" :badge="`${form.invoice_options?.length || 0}`">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs text-muted">
              Ways staff on this profile can raise an invoice, each with its own numbering series and tax template.
              They pick one and preview the number and totals before the invoice is created. Empty = the tax template above and the default series.
            </p>
            <AppButton variant="ghost" size="sm" icon="settings" @click="router.push({ name: 'invoice-options' })">Manage options</AppButton>
          </div>
          <EmptyState v-if="!filteredInvoiceOptions.length" icon="file-text" title="No invoice options yet" description="Create them under Settings → Invoice options." />
          <div v-else class="grid gap-2 md:grid-cols-2">
            <div
              v-for="opt in filteredInvoiceOptions"
              :key="opt.name"
              class="flex items-center gap-3 rounded-2xl border p-3 transition"
              :class="isInvoiceOptionEnabled(opt.name) ? 'border-success/40 bg-success/[0.06]' : 'border-line hover:bg-card-muted'"
            >
              <input type="checkbox" :checked="isInvoiceOptionEnabled(opt.name)" class="h-4 w-4 accent-primary" @change="toggleInvoiceOption(opt.name)" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-semibold text-foreground">{{ opt.option_name }}</p>
                <p class="truncate text-xs text-muted">{{ opt.naming_series }} · {{ opt.taxes_and_charges || 'No tax' }}</p>
                <p class="truncate text-xs text-subtle">{{ opt.available_for_credit === false ? 'Paid now only' : 'Credit' }} · {{ opt.payment_modes?.length ? opt.payment_modes.join(', ') : 'any paid-now mode' }}</p>
              </div>
              <label v-if="isInvoiceOptionEnabled(opt.name)" class="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs font-semibold text-muted">
                <input type="radio" name="default-invoice-option" :checked="isDefaultInvoiceOption(opt.name)" class="accent-primary" @change="setDefaultInvoiceOption(opt.name)" />
                Default
              </label>
            </div>
          </div>
        </FormSection>

        <!-- Printing -->
        <FormSection title="Printing" icon="printer">
          <p class="text-xs text-muted">
            What staff get when they tap Print on a phone. Blank uses the doctype's default format
            and the company's default letter head.
          </p>
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Order print format">
              <BaseSelect :model-value="form.order_print_format ?? ''" @update:model-value="(v) => (form.order_print_format = v)" placeholder="Default (Standard)">
                <option v-for="f in formatsFor('Sales Order')" :key="f.name" :value="f.name">{{ f.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Payment receipt print format">
              <BaseSelect :model-value="form.payment_print_format ?? ''" @update:model-value="(v) => (form.payment_print_format = v)" placeholder="Default (Standard)">
                <option v-for="f in formatsFor('Payment Entry')" :key="f.name" :value="f.name">{{ f.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="!isFieldSales" label="Invoice print format">
              <BaseSelect :model-value="form.invoice_print_format ?? ''" @update:model-value="(v) => (form.invoice_print_format = v)" placeholder="Default (Standard)">
                <option v-for="f in formatsFor('Sales Invoice')" :key="f.name" :value="f.name">{{ f.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="!isFieldSales && form.allow_return" label="Credit note print format" hint="A Sales Invoice format for returns. Blank = the invoice format.">
              <BaseSelect :model-value="form.return_print_format ?? ''" @update:model-value="(v) => (form.return_print_format = v)" placeholder="Same as invoice">
                <option v-for="f in formatsFor('Sales Invoice')" :key="f.name" :value="f.name">{{ f.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Letter head">
              <BaseSelect :model-value="form.letter_head ?? ''" @update:model-value="(v) => (form.letter_head = v)" placeholder="Company default">
                <option v-for="l in options.letter_heads" :key="l.name" :value="l.name">{{ l.name }}{{ l.is_default ? ' (default)' : '' }}</option>
              </BaseSelect>
            </FormField>
          </div>
        </FormSection>

        <!-- Cash movements -->
        <FormSection v-if="form.use_shifts" title="Cash movements (expenses & deposits)" icon="banknote">
          <p class="text-xs text-muted">Cash leaving the drawer mid-shift. Each entry posts a Journal Entry that credits the drawer account and debits the expense or back-office account, and the shift closing deducts it from expected cash.</p>
          <div class="grid gap-2 md:grid-cols-3 [&>label]:rounded-2xl [&>label]:bg-card-muted [&>label]:px-3.5 [&>label]:py-2">
            <ToggleSwitch :model-value="!!form.allow_expense" label="Allow expenses" @update:model-value="(v: boolean) => (form.allow_expense = v)" />
            <ToggleSwitch :model-value="!!form.allow_cash_deposit" label="Allow deposits to office" @update:model-value="(v: boolean) => (form.allow_cash_deposit = v)" />
            <ToggleSwitch :model-value="!!form.require_cash_movement_remarks" label="Require remarks" @update:model-value="(v: boolean) => (form.require_cash_movement_remarks = v)" />
            <ToggleSwitch :model-value="!!form.allow_cancel_cash_movement" label="Staff can cancel their own (while the shift is open)" @update:model-value="(v: boolean) => (form.allow_cancel_cash_movement = v)" />
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <FormField label="Cash drawer account" hint="Blank: the Default Cash Mode's account for this company.">
              <BaseSelect :model-value="form.cash_account ?? ''" @update:model-value="(v) => (form.cash_account = v)" placeholder="From default cash mode">
                <option v-for="a in filteredCashAccounts" :key="a.name" :value="a.name">{{ a.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="form.allow_cash_deposit" label="Back office cash account" hint="Where deposits land. Blank: company default cash account.">
              <BaseSelect :model-value="form.back_office_cash_account ?? ''" @update:model-value="(v) => (form.back_office_cash_account = v)" placeholder="Company default cash account">
                <option v-for="a in filteredCashAccounts" :key="a.name" :value="a.name">{{ a.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField v-if="form.allow_expense" label="Default expense account" hint="Pre-selected on a new expense.">
              <BaseSelect :model-value="form.expense_account ?? ''" @update:model-value="(v) => (form.expense_account = v)" placeholder="None">
                <option v-for="a in selectableExpenseAccounts" :key="a.name" :value="a.name">{{ a.account_name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Cost center" hint="For the Journal Entries. Blank: company default.">
              <BaseSelect :model-value="form.cost_center ?? ''" @update:model-value="(v) => (form.cost_center = v)" placeholder="Company default">
                <option v-for="c in filteredCostCenters" :key="c.name" :value="c.name">{{ c.name }}</option>
              </BaseSelect>
            </FormField>
            <FormField label="Max amount per movement" hint="0 = no limit.">
              <BaseInput :model-value="form.cash_movement_max_amount ?? 0" @update:model-value="(v) => (form.cash_movement_max_amount = Number(v) || 0)" type="number" inputmode="decimal" placeholder="0.00" />
            </FormField>
          </div>
          <template v-if="form.allow_expense">
            <div class="flex items-center justify-between gap-3">
              <p class="text-xs font-bold uppercase tracking-wider text-muted">Allowed expense accounts <span class="font-medium normal-case tracking-normal">· empty = all</span></p>
              <span class="rounded-full bg-card-muted px-2.5 py-1 text-xs font-bold text-muted">{{ form.allowed_expense_accounts?.length || 0 }}</span>
            </div>
            <SearchBar v-model="expenseAccountSearch" placeholder="Filter accounts…" />
            <div class="grid max-h-72 gap-2 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
              <label
                v-for="a in filteredExpenseAccounts"
                :key="a.name"
                class="flex cursor-pointer items-center gap-3 rounded-2xl border p-3 transition"
                :class="(form.allowed_expense_accounts || []).includes(a.name) ? 'border-success/40 bg-success/[0.06]' : 'border-line hover:bg-card-muted'"
              >
                <input type="checkbox" :value="a.name" v-model="form.allowed_expense_accounts" class="h-4 w-4 accent-primary" />
                <span class="truncate text-sm font-semibold text-foreground">{{ a.account_name }}</span>
              </label>
            </div>
          </template>
        </FormSection>

        <!-- Payment modes -->
        <FormSection title="Allowed payment modes" icon="wallet">
          <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <label
              v-for="mode in options.payment_modes"
              :key="mode.name"
              class="flex cursor-pointer items-center gap-3 rounded-2xl border p-3 transition"
              :class="(form.allowed_payment_modes || []).includes(mode.name) ? 'border-success/40 bg-success/[0.06]' : 'border-line hover:bg-card-muted'"
            >
              <input type="checkbox" :value="mode.name" v-model="form.allowed_payment_modes" class="h-4 w-4 accent-primary" />
              <span class="text-sm font-semibold text-foreground">{{ mode.name }}</span>
            </label>
          </div>
          <FormField v-if="form.use_shifts" label="Default cash mode" hint="Which mode counts as the cash drawer for shift reconciliation. Falls back to a cash-type mode above, then the generic &quot;Cash&quot; record, if left blank.">
            <BaseSelect :model-value="form.default_cash_mode ?? ''" @update:model-value="(v) => (form.default_cash_mode = v)" placeholder="Auto-detect">
              <option v-for="mode in allowedCashModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
            </BaseSelect>
          </FormField>
        </FormSection>
      </div>
    </div>

    <StickyBar v-if="selectedProfile">
      <AppButton size="lg" block icon="save" :disabled="!isValid" :loading="isSaving" @click="saveProfile">
        {{ isSaving ? 'Saving…' : selectedProfile.name ? 'Update profile' : 'Save profile' }}
      </AppButton>
    </StickyBar>
  </WorkspacePage>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineComponent, h } from 'vue';
import { useRouter } from 'vue-router';
import { listSalesProfiles, getSalesProfileOptions, saveSalesProfile, deleteSalesProfile } from '../api/frappe';
import type { SalesProfile, SalesProfileOptions } from '../types';
import { useSessionStore } from '../stores/session';
import { useToast } from '../composables/useToast';
import { useConfirm } from '../composables/useConfirm';
import WorkspacePage from '../components/WorkspacePage.vue';
import { AppCard, AppButton, AppAlert, AppIcon, FormField, BaseInput, BaseSelect, SearchBar, StatusBadge, SkeletonList, EmptyState, StickyBar, SegmentedControl, ToggleSwitch } from '../components/ui';

// Collapsible-free section wrapper used throughout the editor.
const FormSection = defineComponent({
  props: { title: { type: String, required: true }, icon: { type: String, required: true }, badge: { type: String, default: '' } },
  setup(props, { slots }) {
    return () =>
      h(AppCard, { padding: 'none' }, () => [
        h('div', { class: 'flex items-center justify-between border-b border-line px-4 py-3 md:px-5' }, [
          h('div', { class: 'flex items-center gap-2.5' }, [
            h('span', { class: 'flex h-8 w-8 items-center justify-center rounded-xl bg-primary/12 text-primary' }, [h(AppIcon, { name: props.icon, size: 16 })]),
            h('h3', { class: 'text-sm font-bold text-foreground' }, props.title),
          ]),
          props.badge ? h('span', { class: 'rounded-full bg-card-muted px-2.5 py-1 text-xs font-bold text-muted' }, props.badge) : null,
        ]),
        h('div', { class: 'space-y-4 p-4 md:p-5' }, slots.default?.()),
      ]);
  },
});

const router = useRouter();
const store = useSessionStore();
const toast = useToast();
const { confirm } = useConfirm();
const currency = computed(() => store.currencyDisplay);
const loading = ref(true);
const isSaving = ref(false);
const isDeleting = ref(false);
const errorMsg = ref('');
const profiles = ref<SalesProfile[]>([]);
const searchQuery = ref('');
const selectedProfile = ref<SalesProfile | Partial<SalesProfile> | null>(null);

const options = ref<SalesProfileOptions>({
  warehouses: [],
  payment_modes: [],
  routes: [],
  customer_groups: [],
  companies: [],
  price_lists: [],
  tax_templates: [],
  invoice_options: [],
  currencies: [],
  print_formats: [],
  letter_heads: [],
  users: [],
  cash_accounts: [],
  expense_accounts: [],
  cost_centers: [],
});

const defaultForm = (): Partial<SalesProfile> => ({
  profile_name: '',
  profile_type: 'Van Sales',
  company: '',
  is_active: true,
  separate_van_warehouse: true,
  source_warehouse: '',
  van_warehouse: '',
  stock_warehouse: '',
  delivery_route: '',
  default_cash_mode: '',
  selling_price_list: '',
  currency: '',
  taxes_and_charges: '',
  apply_discount_on: 'Grand Total',
  daily_credit_limit: 0,
  low_stock_threshold: 5,
  allow_rate_change: false,
  allow_discount_change: false,
  allow_sale_without_stock: false,
  use_shifts: true,
  require_open_shift: false,
  variance_tolerance: 0,
  validate_stock_on_save: false,
  allow_offline_stock_dashboard: true,
  ignore_pricing_rule: false,
  disable_rounded_total: false,
  order_print_format: '',
  invoice_print_format: '',
  return_print_format: '',
  payment_print_format: '',
  letter_head: '',
  income_account: '',
  expense_account: '',
  cost_center: '',
  write_off_account: '',
  allow_expense: true,
  allow_cash_deposit: true,
  cash_account: '',
  back_office_cash_account: '',
  cash_movement_max_amount: 0,
  require_cash_movement_remarks: false,
  allowed_expense_accounts: [],
  invoice_options: [],
  allowed_payment_modes: [],
  allowed_customer_groups: [],
  assigned_drivers: [],
  // POS-profile style controls
  max_discount_percent: 0,
  use_customer_price_list: false,
  allow_zero_rated_items: false,
  allow_credit_sale: true,
  allow_return: true,
  return_validity_days: 0,
  hide_unavailable_items: false,
  show_customer_balance: true,
  allow_create_customer: true,
  allow_duplicate_customer_names: false,
  hide_expected_amount: false,
  allow_driver_close_shift: true,
  allow_cancel_cash_movement: false,
});

const form = ref<Partial<SalesProfile>>(defaultForm());

const filteredProfiles = computed(() => {
  const q = searchQuery.value.toLowerCase();
  return profiles.value.filter((p) => p.profile_name.toLowerCase().includes(q) || p.company.toLowerCase().includes(q));
});
const filteredWarehouses = computed(() =>
  form.value.company ? options.value.warehouses.filter((w) => w.company === form.value.company) : options.value.warehouses,
);
const formatsFor = (doctype: string) => options.value.print_formats.filter((f) => f.doc_type === doctype);
const filteredTaxTemplates = computed(() =>
  form.value.company ? options.value.tax_templates.filter((t) => t.company === form.value.company) : options.value.tax_templates,
);
const expenseAccountSearch = ref('');
const byCompany = <T extends { company: string }>(rows: T[]) =>
  form.value.company ? rows.filter((r) => r.company === form.value.company) : rows;
const filteredCashAccounts = computed(() => byCompany(options.value.cash_accounts || []));
const filteredCostCenters = computed(() => byCompany(options.value.cost_centers || []));
const companyExpenseAccounts = computed(() => byCompany(options.value.expense_accounts || []));
const filteredExpenseAccounts = computed(() => {
  const q = expenseAccountSearch.value.toLowerCase();
  return q ? companyExpenseAccounts.value.filter((a) => a.account_name.toLowerCase().includes(q) || a.name.toLowerCase().includes(q)) : companyExpenseAccounts.value;
});
// The default must be one of the allowed accounts once any are chosen.
const selectableExpenseAccounts = computed(() => {
  const allowed = new Set(form.value.allowed_expense_accounts || []);
  return allowed.size ? companyExpenseAccounts.value.filter((a) => allowed.has(a.name)) : companyExpenseAccounts.value;
});
const allowedCashModes = computed(() => {
  const allowed = new Set(form.value.allowed_payment_modes || []);
  return options.value.payment_modes.filter((m) => m.type === 'Cash' && (allowed.size === 0 || allowed.has(m.name)));
});

const isFieldSales = computed(() => form.value.profile_type === 'Field Sales');

// Switching type resets what the other type can't use, mirroring the server-side
// SalesProfile._validate_profile_type() so the form never shows stale values.
function setProfileType(type: string) {
  form.value.profile_type = type as SalesProfile['profile_type'];
  if (type === 'Field Sales') {
    form.value.source_warehouse = '';
    form.value.van_warehouse = '';
    form.value.allow_sale_without_stock = false;
    form.value.validate_stock_on_save = false;
    form.value.allow_offline_stock_dashboard = false;
    // Field staff default to no shifts; a manager can switch them back on.
    if (!selectedProfile.value?.name) form.value.use_shifts = false;
  } else {
    form.value.stock_warehouse = '';
    if (!selectedProfile.value?.name) form.value.use_shifts = true;
  }
  if (!form.value.use_shifts) form.value.require_open_shift = false;
}

const isValid = computed(() => {
  if (!form.value.profile_name || !form.value.company) return false;
  if (isFieldSales.value) return true;
  if (!form.value.source_warehouse) return false;
  // Without a separate van warehouse the main warehouse is the selling warehouse.
  if (!form.value.separate_van_warehouse) return true;
  return !!form.value.van_warehouse && form.value.source_warehouse !== form.value.van_warehouse;
});

// Invoice options: the master list filtered to the profile's company (options without a
// company fit anywhere); the profile keeps [{invoice_option, is_default}].
const filteredInvoiceOptions = computed(() =>
  (options.value.invoice_options || []).filter((o) => !o.company || !form.value.company || o.company === form.value.company),
);
function isInvoiceOptionEnabled(name: string): boolean {
  return (form.value.invoice_options || []).some((r) => r.invoice_option === name);
}
function isDefaultInvoiceOption(name: string): boolean {
  return (form.value.invoice_options || []).some((r) => r.invoice_option === name && r.is_default);
}
function toggleInvoiceOption(name: string) {
  if (!form.value.invoice_options) form.value.invoice_options = [];
  const rows = form.value.invoice_options;
  const idx = rows.findIndex((r) => r.invoice_option === name);
  if (idx >= 0) rows.splice(idx, 1);
  else rows.push({ invoice_option: name, is_default: false });
  if (rows.length && !rows.some((r) => r.is_default)) rows[0].is_default = true;
}
function setDefaultInvoiceOption(name: string) {
  for (const r of form.value.invoice_options || []) r.is_default = r.invoice_option === name;
}

function isDriverAssigned(username: string): boolean {
  return form.value.assigned_drivers?.some((d) => d.driver_user === username) || false;
}
function toggleDriver(username: string) {
  if (!form.value.assigned_drivers) form.value.assigned_drivers = [];
  const idx = form.value.assigned_drivers.findIndex((d) => d.driver_user === username);
  if (idx >= 0) form.value.assigned_drivers.splice(idx, 1);
  else form.value.assigned_drivers.push({ driver_user: username });
}

async function loadData() {
  loading.value = true;
  try {
    const [optsRes, profilesRes] = await Promise.all([getSalesProfileOptions(), listSalesProfiles()]);
    options.value = optsRes;
    profiles.value = profilesRes;
    if (profiles.value.length > 0 && !selectedProfile.value) selectProfile(profiles.value[0]);
  } catch (err: any) {
    errorMsg.value = err.message || 'Failed to load profiles';
  } finally {
    loading.value = false;
  }
}

function startNew() {
  selectedProfile.value = { ...defaultForm() };
  if (options.value.companies.length === 1) selectedProfile.value.company = options.value.companies[0].name;
  form.value = JSON.parse(JSON.stringify(selectedProfile.value));
  errorMsg.value = '';
}
function selectProfile(p: SalesProfile) {
  selectedProfile.value = p;
  form.value = JSON.parse(JSON.stringify(p));
  errorMsg.value = '';
}

async function saveProfile() {
  if (!isValid.value) return;
  isSaving.value = true;
  errorMsg.value = '';
  try {
    const payload = { ...form.value, assigned_drivers: form.value.assigned_drivers?.map((d) => d.driver_user) || [] };
    const saved = await saveSalesProfile(payload as any);
    const idx = profiles.value.findIndex((p) => p.name === saved.name);
    if (idx >= 0) profiles.value[idx] = saved;
    else profiles.value.push(saved);
    selectProfile(saved);
    toast.success(`Saved ${saved.profile_name}`);
  } catch (err: any) {
    errorMsg.value = err.message || 'Failed to save profile';
  } finally {
    isSaving.value = false;
  }
}

async function removeProfile() {
  const name = selectedProfile.value?.name;
  if (!name) return;
  const ok = await confirm({
    title: `Delete ${form.value.profile_name || name}?`,
    message: 'Staff on this profile lose access to the app until they are assigned to another one.',
    confirmLabel: 'Delete',
    tone: 'danger',
    icon: 'trash',
  });
  if (!ok) return;
  isDeleting.value = true;
  errorMsg.value = '';
  try {
    await deleteSalesProfile(name);
    profiles.value = profiles.value.filter((p) => p.name !== name);
    selectedProfile.value = null;
    toast.success('Profile deleted');
  } catch (err: any) {
    errorMsg.value = err.message || 'Failed to delete profile';
  } finally {
    isDeleting.value = false;
  }
}

onMounted(loadData);
</script>
