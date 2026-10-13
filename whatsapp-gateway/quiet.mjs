/**
 * Keep the dependencies' console output from putting secrets in the journal or log file.
 *
 * The bridge logs through pino at WA_LOG_LEVEL, but libsignal (Baileys' Signal protocol, GPL) prints with the bare console, which no log level governs:
 * session_record.js writes "Closing session:", "Opening session:", "Removing old closed session:"
 * and "Session already closed" with the whole SessionEntry after them — the ratchet's private key,
 * the root and chain keys and the remote identity key, as Buffers, in full. Those lines went to
 * stdout, so into journald, which is persisted and readable by root and the adm group: five such
 * dumps in a morning of one venue's ordinary traffic.
 *
 * The rule here is a whitelist, not a blacklist of libsignal's call sites (which move between
 * versions): console.info and console.debug are dropped altogether (the bridge logs nothing at
 * those levels, and nothing a dependency says there is for the operator), and console.log, .warn
 * and .error keep only arguments that cannot be a key — strings, numbers, booleans, null,
 * undefined — plus an Error's stack (or message). Any other value, including a Buffer, an array
 * and an object, is replaced by "[<Constructor> omitted]". The bridge's own console lines are all
 * strings, so none of ours change.
 *
 * Only node built-ins, so `node --test` checks it in the repo without an install
 * (test/quiet.test.mjs, `npm test`).
 */

const KEPT = new Set(["string", "number", "boolean", "bigint", "undefined"]);

/** One console argument, made safe to print. */
export function scrubArg(value) {
  if (value === null || KEPT.has(typeof value)) return value;
  if (value instanceof Error) return value.stack ?? `${value.name}: ${value.message}`;
  const name = value?.constructor?.name;
  return `[${typeof name === "string" && name ? name : typeof value} omitted]`;
}

/** The arguments of one console call, made safe to print. */
export function scrubArgs(args) {
  return args.map(scrubArg);
}

const QUIETED = Symbol.for("sales-pwa-whatsapp-gateway.quietConsole");
const DROPPED = ["info", "debug", "trace"];
const SCRUBBED = ["log", "warn", "error"];

/**
 * Install the rule on a console-like object (the global console, by default) and return it.
 * Idempotent: a second call does not wrap the wrappers.
 */
export function quietConsole(target = console) {
  if (target[QUIETED]) return target;
  for (const method of DROPPED) {
    if (typeof target[method] === "function") target[method] = () => {};
  }
  for (const method of SCRUBBED) {
    if (typeof target[method] !== "function") continue;
    const original = target[method].bind(target);
    target[method] = (...args) => original(...scrubArgs(args));
  }
  Object.defineProperty(target, QUIETED, { value: true, enumerable: false });
  return target;
}
