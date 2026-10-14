// A minimal IPP (RFC 8010/8011) client: enough to hand a PDF to an office printer.
//
// AirPrint-capable printers (most Brother, HP, Canon, Epson office models since ~2012)
// accept application/pdf on ipp://<host>:631/ipp/print. The request is one HTTP POST
// with content-type application/ipp whose body is: a binary header, attribute
// groups, the end tag, then the document bytes.

import http from 'node:http';

export const OP_PRINT_JOB = 0x0002;
export const OP_GET_PRINTER_ATTRIBUTES = 0x000b;

const TAG = {
  operationAttributes: 0x01,
  end: 0x03,
  integer: 0x21,
  boolean: 0x22,
  enum: 0x23,
  keyword: 0x44,
  uri: 0x45,
  charset: 0x47,
  naturalLanguage: 0x48,
  mimeMediaType: 0x49,
  nameWithoutLanguage: 0x42,
  textWithoutLanguage: 0x41,
};

function attr(tag, name, value) {
  const nameBuf = Buffer.from(name, 'utf8');
  const valueBuf = Buffer.isBuffer(value) ? value : Buffer.from(String(value), 'utf8');
  const out = Buffer.alloc(1 + 2 + nameBuf.length + 2 + valueBuf.length);
  let o = 0;
  out.writeUInt8(tag, o); o += 1;
  out.writeUInt16BE(nameBuf.length, o); o += 2;
  nameBuf.copy(out, o); o += nameBuf.length;
  out.writeUInt16BE(valueBuf.length, o); o += 2;
  valueBuf.copy(out, o);
  return out;
}

/** The bytes of an IPP request. `attributes` is [[tagName, name, value], ...] in order. */
export function encodeRequest({ operation, requestId = 1, attributes, document }) {
  const header = Buffer.alloc(8);
  header.writeUInt8(2, 0); // version 2.0
  header.writeUInt8(0, 1);
  header.writeUInt16BE(operation, 2);
  header.writeUInt32BE(requestId, 4);
  const parts = [header, Buffer.from([TAG.operationAttributes])];
  for (const [tagName, name, value] of attributes) parts.push(attr(TAG[tagName], name, value));
  parts.push(Buffer.from([TAG.end]));
  if (document) parts.push(document);
  return Buffer.concat(parts);
}

export function printJobRequest({ printerUri, jobName, user = 'sales-app', format = 'application/pdf', document, copies = 1, requestId = 1 }) {
  const attributes = [
    ['charset', 'attributes-charset', 'utf-8'],
    ['naturalLanguage', 'attributes-natural-language', 'en'],
    ['uri', 'printer-uri', printerUri],
    ['nameWithoutLanguage', 'requesting-user-name', user],
    ['nameWithoutLanguage', 'job-name', jobName],
    ['mimeMediaType', 'document-format', format],
  ];
  const parts = [encodeRequest({ operation: OP_PRINT_JOB, requestId, attributes })];
  // Job attributes (copies) would need a second group; the agent sends one request per copy instead.
  void copies;
  return Buffer.concat([parts[0], document]);
}

/** {statusCode, ok, message} from an IPP response. Successful codes are 0x0000–0x00ff. */
export function decodeResponse(buf) {
  if (!buf || buf.length < 8) return { statusCode: -1, ok: false, message: 'Short IPP response' };
  const statusCode = buf.readUInt16BE(2);
  const ok = statusCode <= 0x00ff;
  let message = '';
  // status-message, if the printer sends one, is a textWithoutLanguage attribute named status-message.
  let o = 8;
  while (o < buf.length) {
    const tag = buf.readUInt8(o);
    if (tag === TAG.end) break;
    if (tag < 0x10) { o += 1; continue; } // group delimiter
    if (o + 3 > buf.length) break;
    const nameLen = buf.readUInt16BE(o + 1);
    const name = buf.toString('utf8', o + 3, o + 3 + nameLen);
    const valueLenAt = o + 3 + nameLen;
    if (valueLenAt + 2 > buf.length) break;
    const valueLen = buf.readUInt16BE(valueLenAt);
    const value = buf.subarray(valueLenAt + 2, valueLenAt + 2 + valueLen);
    if (name === 'status-message') message = value.toString('utf8');
    o = valueLenAt + 2 + valueLen;
  }
  return { statusCode, ok, message: message || (ok ? 'successful-ok' : `IPP status 0x${statusCode.toString(16).padStart(4, '0')}`) };
}

/** POST one IPP request and resolve with the decoded response. */
export function send({ host, port = 631, path = '/ipp/print', body, timeoutMs = 30000 }) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      { host, port, path, method: 'POST', headers: { 'Content-Type': 'application/ipp', 'Content-Length': body.length }, timeout: timeoutMs },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode} from the printer`));
          resolve(decodeResponse(Buffer.concat(chunks)));
        });
      },
    );
    req.on('timeout', () => req.destroy(new Error('The printer did not answer in time')));
    req.on('error', reject);
    req.end(body);
  });
}
