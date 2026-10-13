import { defineStore } from 'pinia';
import type { UserSession, Capabilities } from '../types';
import * as api from '../api/frappe';
import { useSaleStore } from './sale';
import { useReturnStore } from './returns';
import { useShiftStore } from './shift';

// A manager with no profile keeps the historical behaviour (see utils._capabilities).
const DEFAULT_CAPABILITIES: Capabilities = {
  is_field_sales: false,
  can_invoice: true,
  can_deliver: true,
  can_return: true,
  has_van_warehouse: false,
  can_load_stock: false,
  can_view_stock: false,
  uses_shifts: true,
  requires_open_shift: false,
  can_credit_sale: true,
  can_create_customer: true,
  can_close_shift: true,
  can_cancel_cash_movement: true,
  shows_customer_balance: true,
  blind_shift_close: false,
};

interface State {
  session: UserSession | null;
  loadingSession: boolean;
  currencyCode: string | null;
  currencySymbol: string | null;
}

export const useSessionStore = defineStore('session', {
  state: (): State => ({
    session: null,
    loadingSession: true,
    currencyCode: null,
    currencySymbol: null,
  }),
  getters: {
    currencyDisplay: (state) => state.currencySymbol || state.currencyCode || '₹',
    driverConfig: (state) => state.session?.driver_config || null,
    isManager: (state) => Boolean(state.session?.is_manager),
    isDriver: (state) => Boolean(state.session?.is_driver),
    firstName: (state) => state.session?.full_name?.split(' ')[0] || '',
    capabilities: (state): Capabilities =>
      state.session?.capabilities || state.session?.driver_config?.capabilities || DEFAULT_CAPABILITIES,
    isFieldSales(): boolean {
      return this.capabilities.is_field_sales;
    },
    usesShifts(): boolean {
      return this.capabilities.uses_shifts;
    },
    /** Field Sales never sells from a warehouse, so catalog stock is information only. */
    canOrderWithoutStock(): boolean {
      return this.capabilities.is_field_sales || Boolean(this.driverConfig?.allow_sale_without_stock);
    },
    /** Managers are exempt from the profile's staff controls; a missing profile means "allowed". */
    allowRateChange(): boolean {
      return this.isManager || this.driverConfig?.allow_rate_change !== false;
    },
    allowDiscountChange(): boolean {
      return this.isManager || this.driverConfig?.allow_discount_change !== false;
    },
    maxDiscountPercent(): number {
      return this.isManager ? 0 : Number(this.driverConfig?.max_discount_percent) || 0;
    },
    canCreateCustomer(): boolean {
      return this.isManager || this.capabilities.can_create_customer !== false;
    },
    showsCustomerBalance(): boolean {
      return this.isManager || this.capabilities.shows_customer_balance !== false;
    },
    canCreditSale(): boolean {
      return this.isManager || this.capabilities.can_credit_sale !== false;
    },
    /** What the app is for this person: a van, a field team, or fleet management. */
    workspaceLabel(): string {
      if (this.isManager && !this.driverConfig) return 'Manager';
      return this.driverConfig?.profile_name || (this.isFieldSales ? 'Field Sales' : 'Van Sales');
    },
  },
  actions: {
    async bootstrap() {
      try {
        this.session = await api.getSession();
        await this.fetchCurrency();
        this.hydrateDrafts();
      } catch (e) {
        this.session = null;
      } finally {
        this.loadingSession = false;
      }
    },
    async login(username: string, password: string) {
      this.session = await api.login(username, password);
      await this.fetchCurrency();
      this.hydrateDrafts();
    },
    hydrateDrafts() {
      const user = this.session?.user || null;
      useSaleStore().hydrate(user);
      useReturnStore().hydrate(user);
      useShiftStore().reset();
    },
    async logout(): Promise<string | null> {
      let warning: string | null = null;
      try {
        await api.logout();
      } catch (e: any) {
        warning = e?.message || 'The server did not confirm the sign-out; the local session was cleared.';
      } finally {
        this.session = null;
        useSaleStore().hydrate(null);
        useReturnStore().hydrate(null);
        useShiftStore().reset();
      }
      return warning;
    },
    async fetchCurrency() {
      try {
        const info = await api.getCompanyCurrencyInfo();
        this.currencyCode = info.currency;
        this.currencySymbol = info.symbol;
      } catch (_e) {
        // keep defaults
      }
    },
  },
});
