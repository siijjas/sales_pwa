/**
 * What to do when the WhatsApp socket closes, as a pure decision so it can be tested without a
 * socket. `code` is the DisconnectReason WhatsApp gave (undefined when the close had none),
 * `state` the gateway's state at that moment, `delayMs` the current backoff.
 *
 * Ported from the restaurant app's bridge (apps/restaurant_order/wa-bridge/reconnect.mjs), which
 * learned this on its first live pairing: WhatsApp answers a successful scan with stream error
 * 515 ("restart required") and the phone shows "Logging in…" until the client reconnects with the
 * freshly saved credentials. A gateway that waits out its ordinary backoff — which hours of QR
 * timeouts can grow to a minute — makes the phone give up, unlink the device (401), and the login
 * is wiped. So: 515 reconnects at once, and a close while a QR is showing (WhatsApp times the QR
 * screen out every few minutes, code 408) never grows the backoff; only genuine failures do.
 */
export const RECONNECT_BASE_MS = 2_000;
export const RECONNECT_MAX_MS = 60_000;
export const RESTRICTED_RETRY_MS = 300_000;

// Mirrors Baileys' DisconnectReason; copied so this module imports nothing.
export const CODE = Object.freeze({
  loggedOut: 401,
  forbidden: 403,
  restartRequired: 515,
});

/**
 * @returns {{ state: string, forget: boolean, delayMs: number, nextDelayMs: number }}
 *   state — the gateway state to report until the next connection event;
 *   forget — wipe the saved login before reconnecting (the phone unlinked us);
 *   delayMs — when to reconnect; nextDelayMs — the backoff to carry forward.
 */
export function reconnectPlan({ code, state, delayMs }) {
  if (code === CODE.loggedOut) {
    return { state: 'logged_out', forget: true, delayMs: RECONNECT_BASE_MS, nextDelayMs: RECONNECT_BASE_MS };
  }
  if (code === CODE.forbidden) {
    return { state: 'restricted', forget: false, delayMs: RESTRICTED_RETRY_MS, nextDelayMs: RECONNECT_BASE_MS };
  }
  if (code === CODE.restartRequired) {
    // The pairing handshake: credentials are saved, WhatsApp wants a fresh socket now.
    return { state: 'connecting', forget: false, delayMs: 0, nextDelayMs: RECONNECT_BASE_MS };
  }
  if (state === 'qr') {
    // The QR screen timed out: show a new one promptly, this is not a failure.
    return { state: 'qr', forget: false, delayMs: RECONNECT_BASE_MS, nextDelayMs: delayMs };
  }
  const next = Math.min(Math.max(delayMs, RECONNECT_BASE_MS) * 2, RECONNECT_MAX_MS);
  return { state: state === 'connected' ? 'connecting' : state, forget: false, delayMs, nextDelayMs: next };
}
