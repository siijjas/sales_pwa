// Sales App print agent.
//
// Runs on any computer on the same LAN as the printers (a Windows PC, a Mac, a
// Raspberry Pi) and needs nothing but Node 20+. It polls the Sales App server over
// HTTPS with its token, gets print jobs already rendered for each printer, and pushes
// them to the printers:
//
//   escpos  → the bytes go to the printer's raw port (9100), e.g. Epson TM-T20
//   pdf     → the PDF goes over IPP (631, AirPrint), e.g. a Brother laser; or raw 9100
//             for printers that print PDF files natively
//   system  → either kind, through a printer installed on this computer (USB or
//             network, any driver): see system.mjs. PDFs on Windows need SumatraPDF.
//
// Then it tells the server how it went, so the phone shows "Printed" or the error.
// Nothing listens on this machine: the agent only makes outbound requests.
//
// Configuration comes from the environment (or a .env file next to this script):
//   SP_SERVER_URL    required, the site, e.g. https://erp.example.com
//   SP_AGENT_TOKEN   required, the token of this agent's Sales Print Agent in the desk
//   SP_POLL_MS       poll interval while idle (default: what the server says, 2000)
//   SP_CHECK_MS      how often to check each printer is reachable (default 60000)
//   SP_LOG_LEVEL     debug | info | warn | error (default info)
//   SP_SUMATRA       Windows only: path to SumatraPDF.exe when it is not next to the agent
//
// Every printer the server lists for this agent is served; nothing is configured here.

import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as ipp from './ipp.mjs';
import { hasSystemPrinter, listSystemPrinters, printSystem } from './system.mjs';

export const VERSION = '1.0.0';

const here = path.dirname(fileURLToPath(import.meta.url));
loadDotEnv(path.join(here, '.env'));

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const LOG_LEVEL = LEVELS[(process.env.SP_LOG_LEVEL || 'info').toLowerCase()] || LEVELS.info;
const log = {};
for (const [name, level] of Object.entries(LEVELS)) {
  log[name] = (...args) => {
    if (level >= LOG_LEVEL) console[name === 'debug' ? 'log' : name](new Date().toISOString(), name.toUpperCase(), ...args);
  };
}

function loadDotEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (!m || line.trim().startsWith('#')) continue;
    const value = m[2].replace(/^(['"])(.*)\1$/, '$2');
    if (process.env[m[1]] === undefined) process.env[m[1]] = value;
  }
}

// ---------------------------------------------------------------------------
// The printers
// ---------------------------------------------------------------------------
/** Open a TCP connection, write everything, wait for the printer to take it, close. */
export function sendRaw({ host, port = 9100, data, timeoutMs = 30000 }) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host, port });
    let done = false;
    const finish = (err) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      socket.destroy();
      err ? reject(err) : resolve();
    };
    const timer = setTimeout(() => finish(new Error(`No answer from ${host}:${port} in ${timeoutMs / 1000}s`)), timeoutMs);
    socket.on('error', (e) => finish(new Error(`${host}:${port}: ${e.code || e.message}`)));
    socket.on('connect', () => {
      // end() flushes the write and half-closes; the printer closes once it has read it.
      socket.end(data, () => {
        // Some printers never close their side: once our write buffer is empty the job is in.
        setTimeout(() => finish(), 500);
      });
    });
    socket.on('close', () => finish());
  });
}

/** Resolve true when something answers on host:port, false otherwise (never throws). */
export function reachable({ host, port, timeoutMs = 3000 }) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    const timer = setTimeout(() => { socket.destroy(); resolve(false); }, timeoutMs);
    socket.on('connect', () => { clearTimeout(timer); socket.destroy(); resolve(true); });
    socket.on('error', () => { clearTimeout(timer); resolve(false); });
  });
}

/** Push one job to its printer; resolves when the printer has it, rejects with why not. */
export async function deliver(job, printer) {
  const data = Buffer.from(job.data, 'base64');
  if (!data.length) throw new Error('Empty job');
  if (printer.protocol === 'system') {
    await printSystem({ printer: printer.system_printer, payload: job.payload, data, docName: job.label || job.id });
    return;
  }
  if (printer.protocol === 'ipp') {
    const printerUri = `ipp://${printer.host}:${printer.port}${printer.ipp_path || '/ipp/print'}`;
    const body = ipp.printJobRequest({
      printerUri,
      jobName: job.label || job.id,
      document: data,
      format: job.payload === 'pdf' ? 'application/pdf' : 'application/octet-stream',
    });
    const reply = await ipp.send({ host: printer.host, port: printer.port, path: printer.ipp_path || '/ipp/print', body });
    if (!reply.ok) throw new Error(reply.message);
    return;
  }
  await sendRaw({ host: printer.host, port: printer.port, data });
}

// ---------------------------------------------------------------------------
// The server
// ---------------------------------------------------------------------------
export class Server {
  constructor({ url, token, fetchImpl = fetch }) {
    this.url = url.replace(/\/+$/, '');
    this.token = token;
    this.fetch = fetchImpl;
  }

  async call(method, body, { timeoutMs = 20000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await this.fetch(`${this.url}/api/method/sales_pwa.sales_app.printing.${method}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Sales-Print-Token': this.token },
        body: JSON.stringify(body || {}),
        signal: controller.signal,
      });
      const text = await res.text();
      let data = null;
      try { data = JSON.parse(text); } catch { /* not JSON */ }
      if (!res.ok) {
        const message = data?._server_messages ? serverMessages(data._server_messages) : data?.exception?.split('\n')[0] || text.slice(0, 200);
        throw new Error(`${res.status} ${message || res.statusText}`);
      }
      return data?.message;
    } finally {
      clearTimeout(timer);
    }
  }

  poll(extra) { return this.call('agent_poll', { version: VERSION, host: os.hostname(), ...extra }); }
  report(job, ok, error = '') { return this.call('agent_report', { job, ok: ok ? 1 : 0, error: String(error || '').slice(0, 400) }); }
}

function serverMessages(raw) {
  try {
    return JSON.parse(raw).map((m) => { try { return JSON.parse(m).message; } catch { return m; } }).join(' ').replace(/<[^>]*>/g, '');
  } catch {
    return String(raw);
  }
}

// ---------------------------------------------------------------------------
// The loop
// ---------------------------------------------------------------------------
const where = (p) => (p.protocol === 'system' ? `system printer "${p.system_printer}"` : `${p.protocol}://${p.host}:${p.port}`);

export async function runOnce(server, state) {
  if (!state.listSystemPrinters) state.listSystemPrinters = listSystemPrinters;
  const checks = {};
  const extra = {};
  const now = Date.now();
  if (now - state.lastCheck >= state.checkMs) {
    state.lastCheck = now;
    // What this computer can print on, for the desk's System printer picker.
    try {
      state.systemPrinters = await state.listSystemPrinters();
      extra.system_printers = state.systemPrinters;
    } catch (e) {
      log.debug(`could not list this computer's printers: ${e.message}`);
    }
    await Promise.all(state.printers.map(async (p) => {
      if (p.protocol === 'system') {
        const ok = hasSystemPrinter(state.systemPrinters || [], p.system_printer);
        checks[p.id] = { ok, message: ok ? '' : `no printer named "${p.system_printer}" on ${os.hostname()}` };
        if (!ok) log.warn(`printer ${p.name}: ${checks[p.id].message}`);
        return;
      }
      const ok = await reachable({ host: p.host, port: p.port });
      checks[p.id] = { ok, message: ok ? '' : `nothing answers on ${p.host}:${p.port}` };
      if (!ok) log.warn(`printer ${p.name} (${p.host}:${p.port}) is not reachable`);
    }));
  }
  if (Object.keys(checks).length) extra.printers = checks;
  const reply = await server.poll(extra);
  state.printers = reply.printers || [];
  state.pollMs = Number(process.env.SP_POLL_MS) || reply.poll_ms || state.pollMs;
  const byId = new Map(state.printers.map((p) => [p.id, p]));
  for (const job of reply.jobs || []) {
    const printer = byId.get(job.printer);
    if (!printer) {
      await server.report(job.id, false, 'The agent does not serve this printer');
      continue;
    }
    log.info(`job ${job.id} (${job.label || job.payload}) → ${printer.name} ${where(printer)}`);
    try {
      await deliver(job, printer);
      await server.report(job.id, true);
      log.info(`job ${job.id} printed`);
    } catch (e) {
      log.error(`job ${job.id} failed: ${e.message}`);
      await server.report(job.id, false, e.message);
    }
  }
  return (reply.jobs || []).length;
}

export async function main() {
  const url = process.env.SP_SERVER_URL;
  const token = process.env.SP_AGENT_TOKEN;
  if (!url || !token) {
    console.error('Set SP_SERVER_URL and SP_AGENT_TOKEN (in the environment or in .env next to agent.mjs).');
    process.exit(2);
  }
  const server = new Server({ url, token });
  const state = { printers: [], systemPrinters: [], pollMs: Number(process.env.SP_POLL_MS) || 2000, checkMs: Number(process.env.SP_CHECK_MS) || 60000, lastCheck: 0 };
  log.info(`Sales App print agent ${VERSION} on ${os.hostname()}, server ${server.url}`);
  let failures = 0;
  let announced = false;
  for (;;) {
    let delay = state.pollMs;
    try {
      const printed = await runOnce(server, state);
      if (!announced) {
        announced = true;
        log.info(`connected; serving ${state.printers.length} printer(s): ${state.printers.map((p) => `${p.name} (${where(p)})`).join(', ') || 'none yet'}`);
        if (state.systemPrinters?.length) log.info(`printers on this computer: ${state.systemPrinters.join(', ')}`);
      }
      failures = 0;
      if (printed) delay = 200; // more may be waiting
    } catch (e) {
      failures += 1;
      announced = false;
      delay = Math.min(60000, state.pollMs * 2 ** Math.min(failures, 5));
      log[failures === 1 ? 'warn' : 'debug'](`server unreachable (${e.message}); retrying in ${Math.round(delay / 1000)}s`);
    }
    await new Promise((r) => setTimeout(r, delay));
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
