import { defineStore } from 'pinia';
import type { ActiveShift } from '../types';
import * as api from '../api/frappe';
import { useSessionStore } from './session';

interface ShiftState {
  active: ActiveShift | null;
  loaded: boolean;
  loading: boolean;
}

/**
 * The caller's open shift, shared by Home, the Shift area and every action that
 * needs a shift. Refreshed on demand after opening/closing; cheap to read.
 */
export const useShiftStore = defineStore('shift', {
  state: (): ShiftState => ({ active: null, loaded: false, loading: false }),
  getters: {
    usesShifts: () => useSessionStore().capabilities.uses_shifts,
    isStale: (s) => !!s.active?.is_stale,
    isOpen: (s) => !!s.active && !s.active.is_stale,
    /** Selling is blocked until today's shift is open (Sales Profile.require_open_shift). */
    needsShift(): boolean {
      const caps = useSessionStore().capabilities;
      return this.usesShifts && caps.requires_open_shift && (!this.active || !!this.active.is_stale);
    },
    /** Where to send someone who must deal with their shift first. */
    gateRoute(): { name: string } {
      return { name: this.active?.is_stale ? 'shift-close' : 'shift-open' };
    },
  },
  actions: {
    async refresh(force = false) {
      if (!this.usesShifts) {
        this.active = null;
        this.loaded = true;
        return null;
      }
      if (this.loaded && !force) return this.active;
      this.loading = true;
      try {
        this.active = await api.getActiveShift().catch(() => null);
        this.loaded = true;
      } finally {
        this.loading = false;
      }
      return this.active;
    },
    set(shift: ActiveShift | null) {
      this.active = shift;
      this.loaded = true;
    },
    reset() {
      this.active = null;
      this.loaded = false;
    },
  },
});
