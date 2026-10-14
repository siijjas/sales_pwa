// Printing through the agent's own computer: any printer the operating system knows
// (USB or network, any driver), named as the OS names it.
//
//   Windows   receipts: the bytes go untouched to the queue (win-raw-print.ps1, RAW datatype)
//             PDFs:     SumatraPDF prints them (SumatraPDF.exe next to the agent, or installed)
//   Linux/mac receipts: lp -o raw        PDFs: lp        (CUPS, which also lists the queues)

import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
export const IS_WINDOWS = process.platform === 'win32';

function run(file, args, { timeoutMs = 60000 } = {}) {
  return new Promise((resolve, reject) => {
    execFile(file, args, { timeout: timeoutMs, windowsHide: true, maxBuffer: 1 << 20 }, (err, stdout, stderr) => {
      if (err) {
        if (err.code === 'ENOENT') {
          const hint = file === 'lp' ? ' (install CUPS: cups and cups-client)' : '';
          return reject(new Error(`${path.basename(file)} is not installed on this computer${hint}`));
        }
        const detail = (stderr || stdout || err.message || '').toString().trim().split(/\r?\n/).filter(Boolean).pop() || err.code;
        return reject(new Error(`${path.basename(file)}: ${detail}`));
      }
      resolve((stdout || '').toString());
    });
  });
}

const POWERSHELL = 'powershell.exe';
const psArgs = (...rest) => ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', ...rest];

// --- what the computer can print on ------------------------------------------------------------
export function parseWindowsPrinterList(json) {
  if (!json || !json.trim()) return [];
  const parsed = JSON.parse(json);
  const list = Array.isArray(parsed) ? parsed : [parsed];
  return list.map((p) => (typeof p === 'string' ? p : p?.Name)).filter((n) => typeof n === 'string' && n.trim());
}

export function parseLpstat(output) {
  // `lpstat -e` lists one queue a line; `lpstat -p` says "printer NAME is idle...".
  return output
    .split(/\r?\n/)
    .map((line) => (line.startsWith('printer ') ? line.split(' ')[1] : line.trim()))
    .filter(Boolean);
}

export async function listSystemPrinters() {
  if (IS_WINDOWS) {
    const out = await run(POWERSHELL, psArgs('-Command', '@(Get-Printer | Select-Object -ExpandProperty Name) | ConvertTo-Json -Compress'), { timeoutMs: 30000 });
    return parseWindowsPrinterList(out);
  }
  try {
    return parseLpstat(await run('lpstat', ['-e']));
  } catch {
    return parseLpstat(await run('lpstat', ['-p']).catch(() => ''));
  }
}

// --- the jobs ----------------------------------------------------------------------------------
async function withTempFile(suffix, data, fn) {
  const file = path.join(os.tmpdir(), `sales-app-print-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2)}${suffix}`);
  fs.writeFileSync(file, data, { mode: 0o600 });
  try {
    return await fn(file);
  } finally {
    fs.rm(file, { force: true }, () => {});
  }
}

const SUMATRA_NAMES = ['SumatraPDF.exe', 'SumatraPDF-3.5.2-64.exe', 'SumatraPDF-3.5.2-32.exe'];

/** Where SumatraPDF is: SP_SUMATRA, next to the agent, or the usual install folders. */
export function findSumatra(env = process.env, exists = fs.existsSync) {
  const candidates = [];
  if (env.SP_SUMATRA) candidates.push(env.SP_SUMATRA);
  for (const name of SUMATRA_NAMES) candidates.push(path.join(here, name));
  for (const base of [env.LOCALAPPDATA, env.ProgramFiles, env['ProgramFiles(x86)'], env.ProgramW6432]) {
    if (base) candidates.push(path.join(base, 'SumatraPDF', 'SumatraPDF.exe'));
  }
  return candidates.find((c) => exists(c)) || null;
}

/** The command that prints `file` on `printer`, by platform and payload (pure, for tests). */
export function commandFor({ platform = process.platform, payload, printer, file, docName = 'Sales App', sumatra = null }) {
  if (platform === 'win32') {
    if (payload === 'pdf') {
      if (!sumatra) {
        throw new Error('SumatraPDF.exe is needed to print PDFs on Windows: put it next to agent.mjs (free, https://www.sumatrapdfreader.org) or set SP_SUMATRA');
      }
      return { file: sumatra, args: ['-print-to', printer, '-silent', '-exit-when-done', file] };
    }
    return { file: POWERSHELL, args: psArgs('-File', path.join(here, 'win-raw-print.ps1'), '-PrinterName', printer, '-FilePath', file, '-DocName', docName) };
  }
  const args = ['-d', printer, '-t', docName];
  if (payload !== 'pdf') args.push('-o', 'raw');
  args.push(file);
  return { file: 'lp', args };
}

/** Print `data` on the system printer `printer`; resolves once the spooler has the job. */
export async function printSystem({ printer, payload, data, docName }) {
  if (!printer) throw new Error('No system printer named');
  const suffix = payload === 'pdf' ? '.pdf' : '.bin';
  return withTempFile(suffix, data, async (file) => {
    const cmd = commandFor({ payload, printer, file, docName, sumatra: IS_WINDOWS && payload === 'pdf' ? findSumatra() : null });
    await run(cmd.file, cmd.args, { timeoutMs: 120000 });
  });
}

/** Whether `printer` is one of the computer's printers (case-insensitive), given the list. */
export function hasSystemPrinter(list, printer) {
  const want = String(printer || '').trim().toLowerCase();
  return list.some((n) => n.trim().toLowerCase() === want);
}

