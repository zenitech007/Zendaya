# Mobile API over Tailscale — Setup Runbook

This guide connects the Zendaya Android app (Phase 1) to the PC brain's mobile
API (`/api/v1/*`) over a private Tailscale mesh. No public ports, no port
forwarding, no monthly cost.

## What you get

- The phone reaches the PC at its Tailscale IP (`100.x.y.z`) from anywhere.
- Every mobile request is authenticated with a bearer token.
- Localhost-only behavior is preserved for the existing HUD/pet (they keep
  hitting `127.0.0.1:7475`).

## Prerequisites

- Tailscale installed on **both** the PC and the Android phone, signed into the
  **same** Tailscale account.
- Zendaya backend running on the PC (`backend/zendaya.py`).

## 1. Install Tailscale

- **PC (Windows):** install from <https://tailscale.com/download>, sign in.
- **Android:** install Tailscale from the Play Store, sign in with the same
  account.

Both devices now appear in your tailnet and can reach each other directly.

## 2. Find the PC's Tailscale IP

On the PC:

```powershell
tailscale ip -4
```

This prints a `100.x.y.z` address. That is the host the phone will connect to.

## 3. Generate a mobile token

```powershell
venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output.

## 4. Configure `backend/.env`

Add (or update) these two keys in `backend/.env`:

```
ZENDAYA_MOBILE_TOKEN=<the token from step 3>
ZENDAYA_BIND_HOST=100.x.y.z     # the Tailscale IP from step 2
```

- `ZENDAYA_BIND_HOST` makes uvicorn listen on the Tailscale interface. Binding
  to the specific `100.x` IP keeps the server off other networks. (You can use
  `0.0.0.0` to listen on all interfaces, but the specific Tailscale IP is
  safer.)
- If `ZENDAYA_MOBILE_TOKEN` is empty, the mobile API **fails closed** — every
  request returns 401. This is intentional.

## 5. Restart Zendaya

```powershell
cd backend
..\venv\Scripts\python.exe zendaya.py
```

On startup you should see:

```
🪟 State server: http://127.0.0.1:7475
📱 Mobile API ready at /api/v1 (bind 100.x.y.z; token set).
```

If you see `Mobile API disabled`, the token env var is not set.

## 6. Verify from the phone

Open a browser on the Android phone (with Tailscale connected) and you can do a
quick auth check from any HTTP client. From the PC you can pre-verify:

```powershell
# With token → 200 {"ok":true,"name":"Zendaya"}
curl -H "Authorization: Bearer <TOKEN>" http://100.x.y.z:7475/api/v1/health

# Without token → 401
curl http://100.x.y.z:7475/api/v1/health

# Chat → {"reply":"...","state":"..."}
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" `
     -d '{"message":"what time is it"}' http://100.x.y.z:7475/api/v1/chat
```

## QR pairing (Phase 1)

Typing a 43-character token on a phone is error-prone. The Phase 1 Android app
scans a QR code that encodes the connection details as JSON:

```json
{ "host": "100.x.y.z", "port": 7475, "token": "<the mobile token>" }
```

A small helper to render that QR on the PC will ship with the Phase 1 backend
additions. Until then, the token can be pasted into the app's settings manually.

## History endpoints (Phase 1)

Once the brain has had at least one conversation since Phase 1 shipped:

    # List days that have any messages (newest first)
    curl -H "Authorization: Bearer <TOKEN>" http://<HOST>:7475/api/v1/history/days
    #   -> {"days":[{"day":"2026-06-30","count":12}, ...]}

    # Full transcript for one day (oldest message first)
    curl -H "Authorization: Bearer <TOKEN>" "http://<HOST>:7475/api/v1/history?day=2026-06-30"
    #   -> {"day":"2026-06-30","messages":[{"id":1,"ts":"...","role":"user","text":"...","source":"phone"}, ...]}

Transcripts persist to `backend/zendaya_data/conversations.db` (SQLite). Both
desktop and phone turns are recorded; `source` distinguishes them.

## Troubleshooting

- **Phone gets connection refused:** confirm Tailscale is connected on the phone
  (the app shows "Connected"), and that `ZENDAYA_BIND_HOST` is the Tailscale IP,
  not `127.0.0.1`.
- **Everything returns 401:** the token in the request must exactly match
  `ZENDAYA_MOBILE_TOKEN`. Regenerate and re-paste if unsure.
- **Works on PC localhost but not over Tailscale:** the server is still bound to
  `127.0.0.1`. Check the startup banner shows the `100.x` bind host; restart
  after editing `.env`.
- **HUD/pet stopped working:** they hit `127.0.0.1:7475`, which is unaffected by
  `ZENDAYA_BIND_HOST` only if you bound to `0.0.0.0`. If you bound to the
  specific Tailscale IP, localhost is no longer served — use `0.0.0.0` to serve
  both, or keep the HUD on the same machine via the Tailscale IP.
