import { reactive } from 'vue';

export interface ConfirmOptions {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Danger styles the confirm button red (destructive or irreversible actions). */
  tone?: 'primary' | 'danger' | 'warning';
  icon?: string;
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (ok: boolean) => void;
}

const state = reactive<{ pending: PendingConfirm | null }>({ pending: null });

/**
 * Promise-based confirm dialog, rendered once by ConfirmDialog in the shell:
 *   if (await confirm({ title: 'Clear the cart?', tone: 'danger' })) ...
 */
export function useConfirm() {
  function confirm(options: ConfirmOptions): Promise<boolean> {
    return new Promise((resolve) => {
      state.pending = { confirmLabel: 'Confirm', cancelLabel: 'Cancel', tone: 'primary', ...options, resolve };
    });
  }
  function settle(ok: boolean) {
    state.pending?.resolve(ok);
    state.pending = null;
  }
  return { state, confirm, settle };
}
