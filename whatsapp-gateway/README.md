# WhatsApp gateway

A small Node service that links to a WhatsApp number as a "linked device" (via
[Baileys](https://github.com/WhiskeySockets/Baileys), no browser needed) and
lets the Sales App post messages into a group. Frappe talks to it over a local
HTTP API; the Frappe side is `sales_pwa/sales_app/whatsapp.py` and the
**WhatsApp Settings** page in the desk.

## Run it

```bash
cd apps/sales_pwa/whatsapp-gateway
npm install
cp .env.example .env        # set WA_API_KEY to a long random string
npm start
```

The first start prints a QR in the terminal and also serves it at
`http://127.0.0.1:3010/pair?key=<WA_API_KEY>`. Scan it from the phone that
owns the number (WhatsApp › Linked devices › Link a device), or set `WA_PHONE`
in `.env` to get a pairing code instead. The credentials land in `auth/`
(git-ignored): keep that folder private and back it up if you don't want to
pair again after a reinstall.

Then in the desk open **WhatsApp Settings**, enter the URL and key, save,
and use *Pair device* (shows the same QR), *Pick group* and *Send test message*.

## Keep it running

Any process manager works. With the bench's supervisor, add a program next to
the bench's own (needs sudo):

```ini
[program:sales-pwa-whatsapp]
command=/usr/bin/node server.js
directory=/home/frappe/frappe-bench/apps/sales_pwa/whatsapp-gateway
user=frappe
autostart=true
autorestart=true
stdout_logfile=/home/frappe/frappe-bench/logs/whatsapp-gateway.log
redirect_stderr=true
```

Without sudo, `pm2 start server.js --name whatsapp-gateway` or a
`systemd --user` unit does the same job.

## API

All routes except `/health` need the key: header `x-api-key`, `Authorization:
Bearer`, or `?key=` on the browser routes.

| Route | What it does |
| --- | --- |
| `GET /health` | `{ok, connected}` liveness, no auth |
| `GET /status` | connection state, the paired user, and `qr` (data URL) or `pairing_code` while unpaired |
| `GET /qr.png` | the current pairing QR as an image |
| `GET /pair` | a page that shows the QR / pairing code and refreshes itself |
| `GET /groups` | `{groups: [{id, subject, participants}]}` |
| `POST /send` | `{"to": "<jid or phone>", "text": "..."}` → `{id, to}`. A bare phone number becomes `<digits>@s.whatsapp.net` |
| `POST /logout` | unlinks the device and shows a fresh QR |

`/send` answers 503 while WhatsApp is not connected; Frappe's background job
fails and the message shows up in the Error Log instead of being lost silently.

## Notes

- Bind to `127.0.0.1` (the default) unless Frappe runs on another machine.
- WhatsApp may log the device out (phone reset, "Log out from all devices").
  The gateway then wipes `auth/` and shows a new QR; the desk's *Check
  connection* button tells you when that has happened.
- Automating a personal WhatsApp number is outside WhatsApp's terms; use a
  number dedicated to this purpose, and keep the message volume modest.
