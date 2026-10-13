import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CODE, RECONNECT_BASE_MS, RECONNECT_MAX_MS, reconnectPlan } from '../reconnect.mjs';

test('515 after a scan reconnects at once and resets the backoff', () => {
  const plan = reconnectPlan({ code: CODE.restartRequired, state: 'qr', delayMs: RECONNECT_MAX_MS });
  assert.equal(plan.delayMs, 0);
  assert.equal(plan.nextDelayMs, RECONNECT_BASE_MS);
  assert.equal(plan.forget, false);
  assert.equal(plan.state, 'connecting');
});

test('a QR screen timing out shows a new QR promptly without growing the backoff', () => {
  const plan = reconnectPlan({ code: 408, state: 'qr', delayMs: RECONNECT_BASE_MS });
  assert.equal(plan.delayMs, RECONNECT_BASE_MS);
  assert.equal(plan.nextDelayMs, RECONNECT_BASE_MS);
  assert.equal(plan.state, 'qr');
  let delay = RECONNECT_BASE_MS;
  for (let i = 0; i < 20; i += 1) delay = reconnectPlan({ code: 408, state: 'qr', delayMs: delay }).nextDelayMs;
  assert.equal(delay, RECONNECT_BASE_MS);
});

test('an unlink wipes the login and starts over', () => {
  const plan = reconnectPlan({ code: CODE.loggedOut, state: 'connected', delayMs: 8_000 });
  assert.equal(plan.forget, true);
  assert.equal(plan.state, 'logged_out');
  assert.equal(plan.delayMs, RECONNECT_BASE_MS);
});

test('forbidden backs off for five minutes as restricted', () => {
  const plan = reconnectPlan({ code: CODE.forbidden, state: 'connected', delayMs: 8_000 });
  assert.equal(plan.state, 'restricted');
  assert.equal(plan.delayMs, 300_000);
});

test('other closes while connected double the backoff up to a minute', () => {
  let delay = RECONNECT_BASE_MS;
  const seen = [];
  for (let i = 0; i < 8; i += 1) {
    const plan = reconnectPlan({ code: 428, state: 'connected', delayMs: delay });
    assert.equal(plan.state, 'connecting');
    assert.equal(plan.delayMs, delay);
    seen.push(plan.nextDelayMs);
    delay = plan.nextDelayMs;
  }
  assert.deepEqual(seen, [4_000, 8_000, 16_000, 32_000, 60_000, 60_000, 60_000, 60_000]);
});
