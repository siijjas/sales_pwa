import { strict as assert } from "node:assert";
import { test } from "node:test";
import { quietConsole, scrubArg, scrubArgs } from "../quiet.mjs";

// The shape libsignal prints: session_record.js's `console.info("Closing session:", session)`.
class SessionEntry {
  constructor() {
    this.registrationId = 665430232;
    this.currentRatchet = { rootKey: Buffer.from("00ff", "hex"), ephemeralKeyPair: { privKey: Buffer.alloc(32, 7) } };
    this.indexInfo = { remoteIdentityKey: Buffer.alloc(33, 5), closed: -1 };
  }
}

function recorder() {
  const calls = {};
  const target = {};
  for (const method of ["log", "info", "warn", "error", "debug", "trace"]) {
    calls[method] = [];
    target[method] = (...args) => calls[method].push(args);
  }
  return { target, calls };
}

test("strings, numbers, booleans, null and undefined pass; an Error becomes its stack", () => {
  assert.deepEqual(scrubArgs(["Session already closed", 42, true, null, undefined]), ["Session already closed", 42, true, null, undefined]);
  const error = new Error("webhook answered 502");
  assert.equal(scrubArg(error), error.stack);
  assert.ok(scrubArg(error).includes("webhook answered 502"));
});

test("a session object, a Buffer, an array and a plain object are named, never printed", () => {
  assert.equal(scrubArg(new SessionEntry()), "[SessionEntry omitted]");
  assert.equal(scrubArg(Buffer.alloc(32, 7)), "[Buffer omitted]");
  assert.equal(scrubArg(new Uint8Array(4)), "[Uint8Array omitted]");
  assert.equal(scrubArg([Buffer.alloc(1)]), "[Array omitted]");
  assert.equal(scrubArg({ privKey: "x" }), "[Object omitted]");
  assert.equal(scrubArg(Object.create(null)), "[object omitted]");
  assert.equal(scrubArg(() => {}), "[Function omitted]");
});

test("on a console: info and debug are dropped, warn/log/error are scrubbed, nothing of a key gets through", () => {
  const { target, calls } = recorder();
  assert.equal(quietConsole(target), target);
  const session = new SessionEntry();
  target.info("Closing session:", session); // libsignal session_record.js:273
  target.warn("Session already closed", session); // :270
  target.log("wa-bridge listening on 127.0.0.1:8101");
  target.error("UNHANDLED_REJECTION", new Error("boom").stack);
  target.debug("x", session);
  target.trace("y", session);

  assert.deepEqual(calls.info, []);
  assert.deepEqual(calls.debug, []);
  assert.deepEqual(calls.trace, []);
  assert.deepEqual(calls.warn, [["Session already closed", "[SessionEntry omitted]"]]);
  assert.deepEqual(calls.log, [["wa-bridge listening on 127.0.0.1:8101"]]);
  assert.equal(calls.error.length, 1);
  assert.equal(calls.error[0][0], "UNHANDLED_REJECTION");
  assert.ok(calls.error[0][1].includes("boom"));
  const printed = JSON.stringify(calls);
  assert.ok(!printed.includes("privKey") && !printed.includes("rootKey") && !printed.includes("registrationId"));
});

test("installing twice does not wrap the wrappers", () => {
  const { target, calls } = recorder();
  quietConsole(target);
  const once = target.warn;
  quietConsole(target);
  assert.equal(target.warn, once);
  target.warn(new SessionEntry());
  assert.deepEqual(calls.warn, [["[SessionEntry omitted]"]]);
});
