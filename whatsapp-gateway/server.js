// Sales App WhatsApp gateway.
//
// A small HTTP bridge between Frappe (sales_pwa.sales_app.whatsapp) and WhatsApp,
// built on Baileys (the WhatsApp Web socket library, no browser needed). It pairs
// as a linked device for one WhatsApp number and exposes:
//
//   GET  /health            liveness, no auth
//   GET  /status            connection state, pairing QR (as a data URL) while unpaired
//   GET  /qr.png            the pairing QR as an image
//   GET  /pair              a tiny page that shows the QR and refreshes itself
//   GET  /groups            groups the number belongs to (id + subject)
//   POST /send              {"to": "<jid or phone>", "text": "..."}
//   POST /logout            unlink the device so a new QR is shown
//
// Every route except /health needs the API key: header `x-api-key`, a bearer
// token, or `?key=` for the browser routes.
//
// `state` in /status is one of:
//   connecting   starting, or reconnecting after a drop
//   qr           not paired: a QR (or pairing code) is waiting to be used
//   connected    paired and online; /send works
//   logged_out   the phone unlinked this device; credentials were wiped, pair again
//   restricted   WhatsApp refused the number (403); retried every five minutes
//
// Configuration comes from the environment (or a .env file next to this script):
//   WA_API_KEY   required, shared secret with WhatsApp Settings in Frappe
//   WA_PORT      default 3010
//   WA_HOST      default 127.0.0.1 (keep it local; Frappe runs on the same box)
//   WA_AUTH_DIR  default ./auth, the linked-device credentials (keep private)
//   WA_PHONE     optional, pair with a code instead of a QR (digits with country code)
//   WA_LOG_LEVEL default info; WA_BAILEYS_LOG_LEVEL default warn
//
// The reconnect rules (reconnect.mjs) and the console scrubbing (quiet.mjs) are
// ported from the restaurant app's bridge, which learned them on a live pairing.

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { quietConsole } from './quiet.mjs';
import { RECONNECT_BASE_MS, RECONNECT_MAX_MS, reconnectPlan } from './reconnect.mjs';

// Before anything from Baileys loads: libsignal prints Signal session objects (private keys)
// with the bare console, which no pino level governs. quiet.mjs keeps only plain values.
quietConsole();

const { default: makeWASocket, Browsers, fetchLatestBaileysVersion, useMultiFileAuthState } = await import('@whiskeysockets/baileys');
const { default: pino } = await import('pino');
const { default: QRCode } = await import('qrcode');

const here = path.dirname(fileURLToPath(import.meta.url));
loadDotEnv(path.join(here, '.env'));

const PORT = Number(process.env.WA_PORT || 3010);
const HOST = process.env.WA_HOST || '127.0.0.1';
const API_KEY = process.env.WA_API_KEY || '';
const AUTH_DIR = path.resolve(here, process.env.WA_AUTH_DIR || 'auth');
const PHONE = (process.env.WA_PHONE || '').replace(/\D/g, '');
const BODY_LIMIT = 64 * 1024;

const logger = pino({ level: process.env.WA_LOG_LEVEL || 'info' });
const baileysLogger = pino({ level: process.env.WA_BAILEYS_LOG_LEVEL || 'warn' });

if (!API_KEY) {
  logger.error('WA_API_KEY is not set. Put it in the environment or in whatsapp-gateway/.env');
  process.exit(2);
}

const state = {
  sock: null,
  state: 'connecting', // connecting | qr | connected | logged_out | restricted
  qr: null,
  qrAt: 0,
  pairingCode: null,
  pairingRequested: false,
  user: null,
  lastError: null,
  startedAt: Date.now(),
  connectedAt: 0,
  sent: 0,
  lastSentAt: 0,
};
const groupCache = new Map();
let reconnectTimer = null;
let reconnectDelay = RECONNECT_BASE_MS;
let stopping = false;

// ---------------------------------------------------------------- WhatsApp

/**
 * Forget the login: the directory's CONTENTS, never the directory, which a service
 * manager may have created and which a gateway that removed it cannot always recreate.
 */
function forgetLogin() {
  let entries = [];
  try {
    entries = fs.readdirSync(AUTH_DIR);
  } catch {
    return;
  }
  for (const entry of entries) fs.rmSync(path.join(AUTH_DIR, entry), { recursive: true, force: true });
}

async function connect() {
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (stopping) return;

  fs.mkdirSync(AUTH_DIR, { recursive: true, mode: 0o700 });
  const { state: auth, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));

  const sock = makeWASocket({
    auth,
    version,
    logger: baileysLogger,
    browser: Browsers.ubuntu('Sales App'),
    markOnlineOnConnect: false,
    syncFullHistory: false,
    generateHighQualityLinkPreview: false,
    cachedGroupMetadata: async (jid) => groupCache.get(jid),
  });
  state.sock = sock;
  state.state = 'connecting';
  state.pairingRequested = false;

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    if (sock !== state.sock) return; // a socket /logout or a reconnect already replaced
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      state.state = 'qr';
      state.qr = qr;
      state.qrAt = Date.now();
      if (PHONE && !state.pairingRequested && !auth.creds.registered) {
        state.pairingRequested = true;
        try {
          state.pairingCode = await sock.requestPairingCode(PHONE);
          logger.info({ code: state.pairingCode }, `Pairing code for +${PHONE} (WhatsApp > Linked devices > Link with phone number)`);
        } catch (err) {
          logger.warn({ err }, 'Could not request a pairing code; scan the QR instead');
        }
      } else {
        logger.info('Scan this QR with WhatsApp > Linked devices (or open /pair in a browser):');
        try {
          console.log(await QRCode.toString(qr, { type: 'terminal', small: true }));
        } catch {
          // terminal rendering is a convenience only
        }
      }
    }

    if (connection === 'open') {
      state.state = 'connected';
      state.connectedAt = Date.now();
      state.qr = null;
      state.pairingCode = null;
      state.lastError = null;
      state.user = sock.user || null;
      reconnectDelay = RECONNECT_BASE_MS;
      logger.info({ user: state.user?.id, name: state.user?.name }, 'WhatsApp connected');
    }

    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode;
      const plan = reconnectPlan({ code, state: state.state, delayMs: reconnectDelay });
      logger.warn({ code, from: state.state, to: plan.state, delayMs: plan.delayMs }, 'WhatsApp connection closed');
      state.state = plan.state;
      state.user = null;
      state.lastError = lastDisconnect?.error?.message || `closed (${code ?? 'unknown'})`;
      if (plan.forget) {
        logger.warn('WhatsApp unlinked this device. Credentials removed; pair again.');
        state.qr = null;
        forgetLogin();
      }
      reconnectDelay = plan.nextDelayMs;
      scheduleReconnect(plan.delayMs);
    }
  });
}

/** Every deferred connect() goes through here, so a failure inside it is logged and retried
 * with the ordinary backoff instead of becoming an unhandled rejection in a timer. */
function scheduleReconnect(delayMs) {
  if (stopping) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect().catch((err) => {
      logger.error({ err }, 'Connect failed; retrying');
      if (state.state === 'connected') state.state = 'connecting';
      scheduleReconnect(reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
    });
  }, delayMs);
}

function requireOpen() {
  if (state.state !== 'connected' || !state.sock) {
    const err = new Error(
      state.state === 'qr' ? 'WhatsApp is not paired yet: scan the QR first'
        : state.state === 'logged_out' ? 'WhatsApp unlinked this device: pair again'
          : state.state === 'restricted' ? 'WhatsApp refused this number (restricted)'
            : 'WhatsApp is not connected',
    );
    err.status = 503;
    throw err;
  }
  return state.sock;
}

function toJid(raw) {
  const value = String(raw || '').trim();
  if (!value) {
    const err = new Error('"to" is required');
    err.status = 400;
    throw err;
  }
  if (value.includes('@')) return value;
  const digits = value.replace(/\D/g, '');
  if (digits.length < 7) {
    const err = new Error('"to" must be a WhatsApp JID (…@g.us / …@s.whatsapp.net) or a phone number with country code');
    err.status = 400;
    throw err;
  }
  return `${digits}@s.whatsapp.net`;
}

async function listGroups() {
  const sock = requireOpen();
  const all = await sock.groupFetchAllParticipating();
  const groups = Object.values(all).map((g) => {
    groupCache.set(g.id, g);
    return { id: g.id, subject: g.subject || '', participants: g.participants?.length || 0 };
  });
  groups.sort((a, b) => a.subject.localeCompare(b.subject));
  return groups;
}

async function sendText(to, text) {
  const sock = requireOpen();
  const jid = toJid(to);
  const body = String(text || '').trim();
  if (!body) {
    const err = new Error('"text" is required');
    err.status = 400;
    throw err;
  }
  const result = await sock.sendMessage(jid, { text: body });
  state.sent += 1;
  state.lastSentAt = Date.now();
  return { id: result?.key?.id || null, to: jid };
}

async function statusPayload() {
  const qrPending = state.state === 'qr' && Boolean(state.qr);
  return {
    connected: state.state === 'connected',
    state: state.state,
    user: state.user ? { id: state.user.id, name: state.user.name || '' } : null,
    number: state.user ? (state.user.id || '').split('@')[0].split(':')[0] || null : null,
    qr_pending: qrPending,
    qr: qrPending ? await QRCode.toDataURL(state.qr, { margin: 1, width: 320 }) : null,
    qr_age_seconds: qrPending ? Math.round((Date.now() - state.qrAt) / 1000) : null,
    pairing_code: state.state === 'connected' ? null : state.pairingCode,
    last_error: state.lastError,
    started_at: new Date(state.startedAt).toISOString(),
    connected_at: state.connectedAt ? new Date(state.connectedAt).toISOString() : null,
    sent: state.sent,
    last_sent_at: state.lastSentAt ? new Date(state.lastSentAt).toISOString() : null,
  };
}

// --------------------------------------------------------------------- HTTP

function authorized(req, url) {
  const header = req.headers['x-api-key'];
  const bearer = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  const query = url.searchParams.get('key');
  const given = String(header || bearer || query || '');
  const a = Buffer.from(given);
  const b = Buffer.from(API_KEY);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function json(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(body) });
  res.end(body);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > BODY_LIMIT) {
        const err = new Error('Body too large');
        err.status = 413;
        reject(err);
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (!chunks.length) return resolve({});
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));
      } catch {
        const err = new Error('Body must be JSON');
        err.status = 400;
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

const PAIR_PAGE = `<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sales App WhatsApp</title>
<style>body{font:16px system-ui,sans-serif;margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f6f6;color:#143}
main{text-align:center;padding:24px}img{width:280px;height:280px;background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.08)}
p{margin:12px 0 0;color:#466}code{font-size:28px;letter-spacing:3px}</style>
<main><h1>Sales App WhatsApp</h1><div id="box">Loading…</div></main>
<script>
const key=new URLSearchParams(location.search).get('key')||'';
async function tick(){try{const r=await fetch('/status?key='+encodeURIComponent(key));if(r.status===401){box.innerHTML='<p>Missing or wrong key: open /pair?key=YOUR_API_KEY</p>';return}
const s=await r.json();if(s.connected){box.innerHTML='<p>Connected as <b>'+(s.user?.name||'')+'</b> '+(s.number||'')+'</p><p>You can close this page.</p>'}
else if(s.pairing_code){box.innerHTML='<p>Pairing code</p><code>'+s.pairing_code+'</code><p>WhatsApp › Linked devices › Link with phone number</p>'}
else if(s.qr){box.innerHTML='<img src="'+s.qr+'" alt="QR"><p>WhatsApp › Linked devices › Link a device</p>'}
else{box.innerHTML='<p>'+(s.state+(s.last_error?': '+s.last_error:''))+'</p>'}}catch(e){box.innerHTML='<p>Gateway unreachable</p>'}}
tick();setInterval(tick,4000);
</script>`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  try {
    if (url.pathname === '/health') {
      return json(res, 200, { ok: true, state: state.state, connected: state.state === 'connected' });
    }
    if (!authorized(req, url)) {
      return json(res, 401, { error: 'Unauthorized' });
    }
    if (req.method === 'GET' && url.pathname === '/status') {
      return json(res, 200, await statusPayload());
    }
    if (req.method === 'GET' && url.pathname === '/pair') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      return res.end(PAIR_PAGE);
    }
    if (req.method === 'GET' && url.pathname === '/qr.png') {
      if (state.state !== 'qr' || !state.qr) return json(res, 404, { error: 'No pairing QR right now' });
      const png = await QRCode.toBuffer(state.qr, { margin: 1, width: 320 });
      res.writeHead(200, { 'content-type': 'image/png', 'cache-control': 'no-store' });
      return res.end(png);
    }
    if (req.method === 'GET' && url.pathname === '/groups') {
      return json(res, 200, { groups: await listGroups() });
    }
    if (req.method === 'POST' && url.pathname === '/send') {
      const body = await readJson(req);
      const result = await sendText(body.to, body.text);
      logger.info({ to: result.to, id: result.id }, 'Message sent');
      return json(res, 200, result);
    }
    if (req.method === 'POST' && url.pathname === '/logout') {
      if (state.sock && state.state === 'connected') {
        await state.sock.logout(); // closes with 401 → reconnectPlan forgets the login
      } else {
        forgetLogin();
        state.state = 'connecting';
        state.qr = null;
        try {
          state.sock?.end(undefined);
        } catch {
          // already closed
        }
        reconnectDelay = RECONNECT_BASE_MS;
        scheduleReconnect(0);
      }
      return json(res, 200, { ok: true });
    }
    return json(res, 404, { error: 'Not found' });
  } catch (err) {
    const status = err.status || 500;
    if (status === 503) logger.warn({ path: url.pathname, error: err.message }, 'Request refused');
    else if (status >= 500) logger.error({ err, path: url.pathname }, 'Request failed');
    return json(res, status, { error: err.message || 'Request failed' });
  }
});

server.listen(PORT, HOST, () => {
  logger.info(`Gateway listening on http://${HOST}:${PORT} (auth dir ${AUTH_DIR})`);
  scheduleReconnect(0);
});

// A rejection nothing caught is a bug, not a condition to limp on with: exit non-zero on
// purpose so the service manager (Restart=on-failure) brings a fresh process up.
process.on('unhandledRejection', (reason) => {
  console.error('UNHANDLED_REJECTION', reason instanceof Error ? reason.stack ?? reason.message : String(reason));
  process.exit(1);
});

function shutdown(signal) {
  if (stopping) return;
  stopping = true;
  logger.info(`${signal} received, shutting down`);
  clearTimeout(reconnectTimer);
  server.close();
  try {
    state.sock?.end(undefined);
  } catch {
    // already closed
  }
  setTimeout(() => process.exit(0), 500).unref();
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// ------------------------------------------------------------------ helpers

function loadDotEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}
