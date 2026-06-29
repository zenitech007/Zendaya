# Zendaya Android App — Design

**Date:** 2026-06-29
**Status:** Approved design, pre-implementation
**Goal:** A Siri/Bixby-grade Android companion app for Zendaya, with full mobile
integration and permissions. The phone is a rich client to the existing PC brain;
the PC remains the single source of intelligence.

## Decisions (locked)

- **Platform:** Android only (developer is on Windows; Android allows the deep
  permissions a real assistant needs).
- **Tech stack:** Native Kotlin + Jetpack Compose. Chosen over Flutter/React
  Native because the always-listening wake word, background mic foreground
  service, and Siri-like system permissions are first-class in native Android
  rather than a plugin fight.
- **Connectivity:** Remote-from-anywhere via **Tailscale** (private encrypted
  WireGuard mesh). Phone reaches the PC's Tailscale IP; no public internet
  exposure, no monthly cost.
- **Brain location:** Stays on the Windows PC (`backend/zendaya.py` +
  FastAPI server). The phone does not run its own AI.

## Architecture

```
┌─────────────────────┐         Tailscale mesh          ┌──────────────────────────┐
│   Android Phone      │   (private, encrypted VPN)      │   Windows PC (the brain) │
│  Zendaya app (Kotlin)│ ──────────────────────────────▶ │  FastAPI @ :7475         │
│                      │   HTTPS + WebSocket             │  zendaya.py loop         │
│  • Voice/chat UI     │ ◀────────────────────────────── │  Gemini, TTS, skills     │
│  • Wake-word service │                                 └──────────────────────────┘
│  • Phone permissions │
│  • Talks to PC API   │
└─────────────────────┘
```

The phone is a **rich client**, not a second brain. It sends text/voice to the
PC's chat endpoint, receives replies, and speaks them. *Phone-side* capabilities
(contacts, SMS, location) are exposed back to the brain over the same WebSocket,
so Zendaya's intelligence can request "read my last text" and the phone fulfills
it locally.

### Critical backend change
Today the server binds `127.0.0.1` (localhost only) with **no auth**. For the
phone to reach it over Tailscale we must:
1. Bind to the Tailscale interface (in addition to localhost, so existing
   HUD/pet clients keep working).
2. Add **bearer-token authentication** on all mobile endpoints — non-negotiable,
   since anything on the tailnet could otherwise control the PC.

## Phasing (each phase independently shippable)

| Phase | Delivers | Notes |
|-------|----------|-------|
| **0. Backend prep** | Auth token + bind to Tailscale IP; new `/api/v1/*` mobile router | Foundation; small, low-risk. Build first. |
| **1. Voice + chat client** | Kotlin app: connect, type/talk, hear replies | Proves the pipe end-to-end; usable immediately. |
| **2. Remote PC control** | Trigger PC apps/volume/routines from phone | Reuses existing PC skills via API. |
| **3. Phone-side permissions** | Contacts, SMS, calls, location, calendar exposed to brain | The "Siri on-device" layer. |
| **4. Always-listening wake word** | "Hey Zendaya" hands-free via background service | Hardest (battery, foreground service, on-device wake model). Last. |

Each phase gets its own implementation plan + build cycle. First implementation
target: **Phase 0 → Phase 1.**

## API Contract

New router `backend/server/mobile_api.py`, mounted under `/api/v1/`, all routes
guarded by a `Bearer` token (`ZENDAYA_MOBILE_TOKEN` in `.env`, generated once).
Server bind becomes configurable: localhost + Tailscale IP.

### Phone → brain
| Method | Route | Purpose |
|--------|-------|---------|
| `GET`  | `/api/v1/health` | Reachability + auth check |
| `POST` | `/api/v1/chat` | `{text}` → `{reply, state, tts_url?}` — main turn |
| `WS`   | `/api/v1/stream` | Live state (`thinking`/`speaking`), streamed reply tokens, TTS audio chunks |
| `POST` | `/api/v1/voice` | Upload recorded audio → STT on PC → handled → reply (reuses `_transcribe`) |
| `GET`  | `/api/v1/control/capabilities` | List PC actions the phone can trigger |
| `POST` | `/api/v1/control/action` | `{action, args}` → run a PC skill (open app, volume, routine…) |

### Brain → phone (so Zendaya can use the phone)
The phone registers a callback channel over the same WebSocket. When the brain
decides to use a phone feature, it sends a `phone_request` frame; the app
fulfills it locally and returns the result. No inbound ports on the phone — all
over the existing WS.

## Security

- **Auth:** Single shared bearer token, generated on the PC, paired to the app
  once via **QR code** (avoids typing a long token). Every request and WS
  handshake must carry it.
- **Transport:** Tailscale encrypts end-to-end (WireGuard) — TLS-equivalent
  privacy with no cert management.
- **Blast radius:** Token gates all mobile endpoints. Destructive PC actions
  (shutdown, file delete) keep their existing confirmation gates; the phone
  cannot bypass them.
- **Phone permissions:** Requested at runtime, least-privilege, each feature
  degrades gracefully if denied.

## Phone-Side Permissions (Phase 3)

Each maps to an Android runtime permission + a handler the brain can invoke:
- Contacts (`READ_CONTACTS`) — "call Mom" resolves a number
- SMS (`READ_SMS` / `SEND_SMS`) — read/send texts
- Calls (`CALL_PHONE`) — place calls
- Location (`ACCESS_FINE_LOCATION`) — "where am I", location-aware answers
- Calendar (`READ_CALENDAR` / `WRITE_CALENDAR`) — phone calendar events
- Notifications (`POST_NOTIFICATIONS`) — Zendaya speaks/pushes alerts

## Always-Listening Wake Word (Phase 4)

- On-device wake detection (Porcupine Android SDK or a TFLite openWakeWord port)
  running in a **foreground service** with a persistent notification (Android
  requirement).
- On wake → record utterance → send to PC `/api/v1/voice` → speak reply.
- Battery/privacy: wake model runs locally; only the post-wake utterance leaves
  the device. User toggle to disable.

## Error Handling

- **Offline/unreachable PC:** app shows "Zendaya's brain is offline," retries WS
  with exponential backoff, never silently drops a destructive action.
- **Auth failure:** clear re-pair prompt (re-scan QR).
- **Permission denied:** feature disabled gracefully with an explanation.

## Testing

- **Backend:** pytest for the new `mobile_api` router — auth pass/fail, action
  dispatch, mocked skills, callback framing.
- **App:** Kotlin unit tests for the API/WS client; JUnit/Robolectric for
  permission handlers; manual on-device testing for mic + wake word.

## Out of Scope (v1)

- iOS (Android-only by decision).
- Cloud-hosted brain / standalone on-phone AI.
- Public-internet exposure of the PC (Tailscale only).
