import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { commandFor, findSumatra, hasSystemPrinter, parseLpstat, parseWindowsPrinterList, printSystem } from '../system.mjs';
import { Server, runOnce } from '../agent.mjs';

test('printer lists parse on both platforms', () => {
  assert.deepEqual(parseWindowsPrinterList('["Brother HL-L2350DW series","EPSON TM-T20III Receipt"]'), ['Brother HL-L2350DW series', 'EPSON TM-T20III Receipt']);
  assert.deepEqual(parseWindowsPrinterList('"Only One"'), ['Only One']); // ConvertTo-Json drops the array for one item
  assert.deepEqual(parseWindowsPrinterList('[{"Name":"A"},{"Name":"B"}]'), ['A', 'B']);
  assert.deepEqual(parseWindowsPrinterList(''), []);
  assert.deepEqual(parseLpstat('Brother_HL\nEPSON_TM\n'), ['Brother_HL', 'EPSON_TM']);
  assert.deepEqual(parseLpstat('printer Brother_HL is idle.  enabled since Mon\nprinter EPSON_TM disabled since Tue'), ['Brother_HL', 'EPSON_TM']);
  assert.equal(hasSystemPrinter(['EPSON TM-T20III Receipt'], 'epson tm-t20iii receipt '), true);
  assert.equal(hasSystemPrinter(['EPSON'], 'Brother'), false);
});

test('the print command matches the platform and the payload', () => {
  const raw = commandFor({ platform: 'win32', payload: 'escpos', printer: 'EPSON', file: 'C:\\t\\j.bin', docName: 'Receipt 1' });
  assert.equal(raw.file, 'powershell.exe');
  assert.ok(raw.args.includes('-File') && raw.args.some((a) => a.endsWith('win-raw-print.ps1')));
  assert.deepEqual(raw.args.slice(-6), ['-PrinterName', 'EPSON', '-FilePath', 'C:\\t\\j.bin', '-DocName', 'Receipt 1']);
  const pdf = commandFor({ platform: 'win32', payload: 'pdf', printer: 'Brother', file: 'C:\\t\\j.pdf', sumatra: 'C:\\s\\SumatraPDF.exe' });
  assert.deepEqual(pdf, { file: 'C:\\s\\SumatraPDF.exe', args: ['-print-to', 'Brother', '-silent', '-exit-when-done', 'C:\\t\\j.pdf'] });
  assert.throws(() => commandFor({ platform: 'win32', payload: 'pdf', printer: 'Brother', file: 'x.pdf', sumatra: null }), /SumatraPDF/);
  assert.deepEqual(commandFor({ platform: 'linux', payload: 'escpos', printer: 'EPSON_TM', file: '/tmp/j.bin', docName: 'R' }), { file: 'lp', args: ['-d', 'EPSON_TM', '-t', 'R', '-o', 'raw', '/tmp/j.bin'] });
  assert.deepEqual(commandFor({ platform: 'darwin', payload: 'pdf', printer: 'Brother', file: '/tmp/j.pdf', docName: 'Inv' }), { file: 'lp', args: ['-d', 'Brother', '-t', 'Inv', '/tmp/j.pdf'] });
});

test('SumatraPDF is found from the env, next to the agent, or in Program Files', () => {
  const exists = (p) => p === path.join('C:\\PF', 'SumatraPDF', 'SumatraPDF.exe');
  assert.equal(findSumatra({ ProgramFiles: 'C:\\PF' }, exists), path.join('C:\\PF', 'SumatraPDF', 'SumatraPDF.exe'));
  assert.equal(findSumatra({ SP_SUMATRA: 'D:\\s.exe' }, (p) => p === 'D:\\s.exe'), 'D:\\s.exe');
  assert.equal(findSumatra({}, () => false), null);
});

const skipOnWindows = process.platform === 'win32';

test('a system job runs lp with the bytes in a temp file that is removed afterwards', { skip: skipOnWindows }, async () => {
  const bin = fs.mkdtempSync(path.join(os.tmpdir(), 'fake-lp-'));
  const log = path.join(bin, 'calls.log');
  fs.writeFileSync(path.join(bin, 'lp'), `#!/bin/sh\nprintf '%s\\n' "$*" >> "${log}"\nfor a in "$@"; do f="$a"; done\ncat "$f" >> "${log}.data"\n`, { mode: 0o755 });
  const oldPath = process.env.PATH;
  process.env.PATH = `${bin}:${oldPath}`;
  try {
    await printSystem({ printer: 'EPSON_TM', payload: 'escpos', data: Buffer.from('\x1b@receipt'), docName: 'Receipt 9' });
    const call = fs.readFileSync(log, 'utf8').trim();
    assert.match(call, /^-d EPSON_TM -t Receipt 9 -o raw \S+sales-app-print-\S+\.bin$/);
    assert.equal(fs.readFileSync(`${log}.data`, 'latin1'), '\x1b@receipt');
    const tempFile = call.split(' ').pop();
    await new Promise((r) => setTimeout(r, 50));
    assert.equal(fs.existsSync(tempFile), false);
  } finally {
    process.env.PATH = oldPath;
    fs.rmSync(bin, { recursive: true, force: true });
  }
});

test('a missing lp (no CUPS) fails the job with a readable reason', { skip: skipOnWindows }, async () => {
  const oldPath = process.env.PATH;
  process.env.PATH = fs.mkdtempSync(path.join(os.tmpdir(), 'empty-path-'));
  try {
    await assert.rejects(printSystem({ printer: 'X', payload: 'pdf', data: Buffer.from('%PDF') }), /lp is not installed on this computer/);
  } finally {
    process.env.PATH = oldPath;
  }
});

test('the poll reports this computer\'s printers and whether a system printer is installed', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push(JSON.parse(init.body));
    return new Response(JSON.stringify({ message: { agent: 'Shop', poll_ms: 2000, printers: [
      { id: 'Brother', name: 'Brother', type: 'pdf', protocol: 'system', system_printer: 'Brother HL-L2350DW series' },
      { id: 'Ghost', name: 'Ghost', type: 'pdf', protocol: 'system', system_printer: 'Nope' },
    ], jobs: [] } }), { status: 200 });
  };
  const server = new Server({ url: 'https://erp.test', token: 't', fetchImpl });
  const state = { printers: [], pollMs: 2000, checkMs: 0, lastCheck: 0, listSystemPrinters: async () => ['Brother HL-L2350DW series', 'Microsoft Print to PDF'] };
  await runOnce(server, state);
  assert.deepEqual(calls[0].system_printers, ['Brother HL-L2350DW series', 'Microsoft Print to PDF']);
  await runOnce(server, state); // now it knows its printers
  assert.equal(calls[1].printers.Brother.ok, true);
  assert.equal(calls[1].printers.Ghost.ok, false);
  assert.match(calls[1].printers.Ghost.message, /no printer named "Nope"/);
});
