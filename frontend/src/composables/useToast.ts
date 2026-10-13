import { reactive } from 'vue';

export type ToastTone = 'success' | 'danger' | 'info' | 'warning';

export interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  message?: string;
  /** Optional action rendered as a text button. */
  action?: { label: string; run: () => void };
  duration: number;
}

const state = reactive<{ toasts: Toast[] }>({ toasts: [] });
let seq = 0;

function push(tone: ToastTone, title: string, opts: { message?: string; action?: Toast['action']; duration?: number } = {}) {
  const id = ++seq;
  const toast: Toast = { id, tone, title, message: opts.message, action: opts.action, duration: opts.duration ?? (tone === 'danger' ? 6000 : 3500) };
  state.toasts.push(toast);
  if (state.toasts.length > 3) state.toasts.shift();
  window.setTimeout(() => dismiss(id), toast.duration);
  return id;
}

function dismiss(id: number) {
  const idx = state.toasts.findIndex((t) => t.id === id);
  if (idx > -1) state.toasts.splice(idx, 1);
}

/**
 * One global toast queue. Success and informational outcomes go here (the screen
 * moves on); errors that block an action stay inline next to that action.
 */
export function useToast() {
  return {
    toasts: state.toasts,
    success: (title: string, opts?: Parameters<typeof push>[2]) => push('success', title, opts),
    error: (title: string, opts?: Parameters<typeof push>[2]) => push('danger', title, opts),
    info: (title: string, opts?: Parameters<typeof push>[2]) => push('info', title, opts),
    warning: (title: string, opts?: Parameters<typeof push>[2]) => push('warning', title, opts),
    dismiss,
  };
}
