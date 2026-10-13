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

`deploy/sales-pwa-whatsapp.service` is a `systemd --user` unit for the bench
account, no root needed:

```bash
mkdir -p ~/.config/systemd/user
cp apps/sales_pwa/deploy/sales-pwa-whatsapp.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sales-pwa-whatsapp
journalctl --user -u sales-pwa-whatsapp -f
```

Run `loginctl enable-linger $USER` once so it keeps running while nobody is
logged in. The unit reads `.env`; set `WA_NODE` there if the node on its PATH
is older than 20. It restarts the gateway on failure, and the gateway exits on
purpose on any unhandled rejection so a restart is always clean.

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

`state` is `connecting`, `qr` (waiting for a scan), `connected`, `logged_out`
(the phone unlinked the device; credentials wiped, pair again) or `restricted`
(WhatsApp refused the number; retried every five minutes). Frappe polls this
every minute and shows it at the top of WhatsApp Settings.

## How it reconnects

`reconnect.mjs` decides every close, ported from the restaurant app's bridge
after its first live pairing: a successful scan is answered by WhatsApp with
stream error 515 and needs an immediate reconnect, or the phone gives up and
unlinks the device; a QR timing out (408) never grows the backoff; 401 forgets
the login; 403 waits five minutes; anything else doubles the delay up to a
minute. `quiet.mjs` keeps libsignal from printing session keys through the bare
console into the journal. Both are pure modules with `npm test` suites.

## Notes

- Bind to `127.0.0.1` (the default) unless Frappe runs on another machine.
- WhatsApp may log the device out (phone reset, "Log out from all devices").
  The gateway then wipes `auth/` and shows a new QR; the desk's *Check
  connection* button tells you when that has happened.
- Automating a personal WhatsApp number is outside WhatsApp's terms; use a
  number dedicated to this purpose, and keep the message volume modest.
