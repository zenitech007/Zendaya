# Zendaya Android app — build & install

How to turn the `android/` source into an APK on your phone, pair it with the PC brain, and use text chat + history. No local Android toolchain is required — the APK is built in the cloud by GitHub Actions.

## Prerequisites

- **Tailscale** installed and connected on **both** the PC and the phone (same tailnet).
- On the PC `.env`:
  - `ZENDAYA_MOBILE_TOKEN` — a long random secret (the phone authenticates with this).
  - `ZENDAYA_BIND_HOST` — the PC's Tailscale IP (`tailscale ip -4`). Use `0.0.0.0` if the local HUD/pet must also keep working; `127.0.0.1` will NOT be reachable from the phone.
- GitHub Actions enabled on the repo (needs a non-locked billing account).

## 1. Build (cloud)

Trigger the **"Android build"** workflow, either by:

- pushing to the branch, or
- **GitHub → Actions → Android build → Run workflow**.

Wait ~3–5 minutes for the run to go green.

> If a run shows *"job not started: account locked due to a billing issue"*, fix billing at github.com/settings/billing, then **re-run the failed workflow** (no new push needed).

## 2. Download the APK

1. Open the finished run.
2. **Artifacts → `zendaya-debug-apk`** → download the zip.
3. Extract `app-debug.apk`.
4. Transfer it to the phone — Tailscale Taildrop, Google Drive, or USB.

## 3. Install on the phone

1. Enable **"Install unknown apps"** for your file manager / browser.
2. Tap `app-debug.apk` → **Install**.

## 4. Pair

1. Make sure Tailscale is **connected** on the phone.
2. On the PC, confirm `ZENDAYA_BIND_HOST` (Tailscale IP or `0.0.0.0`) and `ZENDAYA_MOBILE_TOKEN` are set, then **restart Zendaya**.
3. Run the pairing helper:
   ```
   cd backend
   ..\venv\Scripts\python.exe tools\pair_qr.py
   ```
   It prints the pairing JSON and, if `qrcode` is installed, a scannable ASCII QR.
4. In the app, tap **Scan QR code** and scan it.

## 5. Use

- Type a message → a reply bubble appears from the brain.
- Tap the **History** icon → pick a day → see the full transcript, with `source` labels for desktop vs. phone turns.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Brain unreachable" | Check Tailscale is up on both ends; confirm `ZENDAYA_BIND_HOST` is the Tailscale IP or `0.0.0.0`, not `127.0.0.1`; confirm Zendaya is running. |
| Pairing rejected | Re-run `pair_qr.py`; ensure the app's token matches the current `ZENDAYA_MOBILE_TOKEN` (re-pair after any token change). |
| Empty history | Have at least one conversation since Phase 1 shipped — older turns predate the transcript store. |
| `pair_qr.py` prints a localhost warning | `ZENDAYA_BIND_HOST` is `127.0.0.1`/`localhost`; set it to the Tailscale IP (or `0.0.0.0`) and restart. |
