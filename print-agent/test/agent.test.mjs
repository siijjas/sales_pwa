import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import http from 'node:http';
import * as ipp from '../ipp.mjs';
import { Server, deliver, reachable, runOnce, sendRaw } from '../agent.mjs';

const listen = (server) => new Promise((r) => server.listen(0, '127.0.0.1', () => r(server.address().port)));

// A fake ESC/POS printer: swallows bytes on a raw port and closes when the client ends.
function rawPrinter() {
  const received = [];
  const server = net.createServer((socket) => {
    const chunks = [];
    socket.on('data', (c) => chunks.push(c));
    socket.on('end', () => { received.push(Buffer.concat(chunks)); socket.end(); });
  });
  return { server, received };
}

// A fake IPP printer: answers every Print-Job with successful-ok (or a chosen status).
function ippPrinter(statusCode = 0x0000) {
  const requests = [];
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      requests.push({ headers: req.headers, path: req.url, body: Buffer.concat(chunks) });
      const reply = Buffer.alloc(9);
      reply.writeUInt8(2, 0); reply.writeUInt16BE(statusCode, 2); reply.writeUInt32BE(1, 4); reply.writeUInt8(0x03, 8);
      res.writeHead(200, { 'Content-Type': 'application/ipp' });
      res.end(reply);
    });
  });
  return { server, requests };
}

test('IPP Print-Job request carries the header, the attributes and the document', () => {
  const body = ipp.printJobRequest({ printerUri: 'ipp://p:631/ipp/print', jobName: 'Invoice 1', document: Buffer.from('%PDF-1.4') });
  assert.equal(body.readUInt8(0), 2); // version 2.0
  assert.equal(body.readUInt16BE(2), ipp.OP_PRINT_JOB);
  assert.equal(body.readUInt8(8), 0x01); // operation attributes group
  const text = body.toString('latin1');
  assert.ok(text.includes('attributes-charset') && text.includes('utf-8'));
  assert.ok(text.includes('printer-uri') && text.includes('ipp://p:631/ipp/print'));
  assert.ok(text.includes('document-format') && text.includes('application/pdf'));
  assert.ok(text.endsWith('\x03%PDF-1.4'));
});

test('IPP responses decode their status and message', () => {
  const ok = Buffer.from([2, 0, 0x00, 0x00, 0, 0, 0, 1, 0x03]);
  assert.deepEqual(ipp.decodeResponse(ok), { statusCode: 0, ok: true, message: 'successful-ok' });
  const name = Buffer.from('status-message'), value = Buffer.from('Out of paper');
  const bad = Buffer.concat([
    Buffer.from([2, 0, 0x05, 0x06, 0, 0, 0, 1, 0x01, 0x41]), Buffer.from([0, name.length]), name, Buffer.from([0, value.length]), value, Buffer.from([0x03]),
  ]);
  assert.deepEqual(ipp.decodeResponse(bad), { statusCode: 0x0506, ok: false, message: 'Out of paper' });
  assert.equal(ipp.decodeResponse(Buffer.from([2, 0, 0x04, 0x00, 0, 0, 0, 1, 0x03])).message, 'IPP status 0x0400');
});

test('a raw job reaches the printer byte for byte', async () => {
  const printer = rawPrinter();
  const port = await listen(printer.server);
  const data = Buffer.from('\x1b@hello\x1dV\x42\x00', 'latin1');
  await deliver({ id: 'J1', data: data.toString('base64'), payload: 'escpos' }, { host: '127.0.0.1', port, protocol: 'raw' });
  printer.server.close();
  assert.equal(printer.received.length, 1);
  assert.deepEqual(printer.received[0], data);
});

test('a pdf job goes over IPP to the printer path and a bad status fails it', async () => {
  const good = ippPrinter();
  const port = await listen(good.server);
  await deliver({ id: 'J2', label: 'Invoice 7', data: Buffer.from('%PDF-1.4 x').toString('base64'), payload: 'pdf' }, { host: '127.0.0.1', port, protocol: 'ipp', ipp_path: '/ipp/print' });
  good.server.close();
  assert.equal(good.requests.length, 1);
  assert.equal(good.requests[0].path, '/ipp/print');
  assert.equal(good.requests[0].headers['content-type'], 'application/ipp');
  assert.ok(good.requests[0].body.toString('latin1').endsWith('%PDF-1.4 x'));

  const bad = ippPrinter(0x0400);
  const badPort = await listen(bad.server);
  await assert.rejects(
    deliver({ id: 'J3', data: Buffer.from('x').toString('base64'), payload: 'pdf' }, { host: '127.0.0.1', port: badPort, protocol: 'ipp' }),
    /IPP status 0x0400/,
  );
  bad.server.close();
});

test('an unreachable printer fails fast with the address in the message', async () => {
  const closed = net.createServer();
  const port = await listen(closed);
  await new Promise((r) => closed.close(r));
  await assert.rejects(sendRaw({ host: '127.0.0.1', port, data: Buffer.from('x'), timeoutMs: 2000 }), new RegExp(`127.0.0.1:${port}`));
  assert.equal(await reachable({ host: '127.0.0.1', port, timeoutMs: 500 }), false);
});

test('one poll prints every job it gets and reports each outcome', async () => {
  const printer = rawPrinter();
  const port = await listen(printer.server);
  const calls = [];
  const fetchImpl = async (url, init) => {
    const body = JSON.parse(init.body);
    calls.push({ url, body, token: init.headers['X-Sales-Print-Token'] });
    if (url.endsWith('agent_poll')) {
      return new Response(JSON.stringify({ message: {
        agent: 'Shop', poll_ms: 1500,
        printers: [{ id: 'Epson', name: 'Epson', type: 'escpos', host: '127.0.0.1', port, protocol: 'raw' }],
        jobs: [
          { id: 'PRN-1', printer: 'Epson', label: 'Receipt', payload: 'escpos', data: Buffer.from('abc').toString('base64') },
          { id: 'PRN-2', printer: 'Ghost', label: 'Lost', payload: 'escpos', data: Buffer.from('zzz').toString('base64') },
        ],
      } }), { status: 200 });
    }
    return new Response(JSON.stringify({ message: { ok: true } }), { status: 200 });
  };
  const server = new Server({ url: 'https://erp.test/', token: 'tok', fetchImpl });
  const state = { printers: [], pollMs: 2000, checkMs: 60000, lastCheck: 0 };
  const printed = await runOnce(server, state);
  printer.server.close();
  assert.equal(printed, 2);
  assert.equal(state.pollMs, 1500);
  assert.equal(calls[0].url, 'https://erp.test/api/method/sales_pwa.sales_app.printing.agent_poll');
  assert.equal(calls[0].token, 'tok');
  assert.equal(calls[0].body.version.length > 0, true);
  const reports = calls.filter((c) => c.url.endsWith('agent_report')).map((c) => c.body);
  assert.deepEqual(reports.map((r) => [r.job, r.ok]), [['PRN-1', 1], ['PRN-2', 0]]);
  assert.match(reports[1].error, /does not serve/);
  assert.deepEqual(printer.received[0], Buffer.from('abc'));

  // The next poll, once the check interval is due, reports the printers' reachability.
  state.lastCheck = 0;
  calls.length = 0;
  await runOnce(server, state);
  assert.equal(calls[0].body.printers.Epson.ok, false); // the fake printer is closed now
});

test('a server error surfaces its message', async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ exception: 'frappe.exceptions.AuthenticationError: Unknown agent token.' }), { status: 401 });
  const server = new Server({ url: 'https://erp.test', token: 'bad', fetchImpl });
  await assert.rejects(server.poll(), /401 .*Unknown agent token/);
});
