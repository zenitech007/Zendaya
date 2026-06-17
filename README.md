# Zendaya — Offline-First Desktop Voice Assistant

Zendaya is a local **Windows desktop voice assistant** with a Google Gemini brain,
offline-capable speech, persistent memory, and a set of skills for controlling the
machine and a few external services. It runs **headless** (no GUI) — you talk to it,
it talks back.

> This repo is **backend-only**. Earlier HUD/pet/Unity/Flutter frontends and an
> alternate FastAPI+Supabase backend were removed; everything here is the live
> Python assistant under `backend/`.

---

## Features

- **Brain** — Google Gemini (via `google-genai`) for conversation and reasoning.
- **Voice in** — custom **"Zendaya"/"Zen"** wake words (openWakeWord, trained via the
  free Colab guide in `docs/superpowers/guides/wake-training-colab.md`) → VAD (Silero) +
  denoise → Whisper STT. Falls back to `hey_jarvis` until the models are trained.
- **Conversation flow** — talk over her to interrupt (`ZENDAYA_BARGE_MODE=acoustic|wake|off`,
  `ZENDAYA_BARGE_MARGIN`), a follow-up window so you can chain turns without re-waking
  (`ZENDAYA_FOLLOWUP_S`, default 10s; cue via `ZENDAYA_FOLLOWUP_CUE`), and backchannels on
  long tasks (`ZENDAYA_BACKCHANNEL`).
- **Voice out** — **offline-first**: Coqui TTS (VITS) is the default voice; ElevenLabs
  is available on demand; `pyttsx3` is the last-resort fallback. Switch at runtime
  with `/voice offline | elevenlabs`.
- **Memory** — JSON fact store + conversation history (optional Chroma vector memory).
- **Skills** — coder, browser automation, journal, scheduler, alarms/timers/lists,
  proactive alerts, plus integrations for Spotify, Home Assistant, phone (KDE Connect),
  and GitHub.
- **Perception** — webcam face/gesture awareness, screen/window awareness, and
  on-screen UI vision control (screenshot + Gemini vision + pyautogui).
- **Local API** — a FastAPI "state server" on `127.0.0.1:7475` exposes `/health`,
  `/chat`, `/quit`, and the audio/viseme stream (used by the supervisor; no GUI needed).

---

## Project structure

```
backend/
├── zendaya.py            # main assistant loop (entrypoint, run by the launcher)
├── zendaya_launcher.py   # process supervisor (spawn, health-check, restart, --quit)
├── requirements.txt              # backend deps (pinned)
├── requirements-offline-voice.txt# offline-TTS extras (torchcodec; eSpeak-NG is a system dep)
├── voice/         # wake, vad_silero, denoise, agc, listener, listener_v2, visemes, offline_tts
├── server/        # state_server (FastAPI bridge), hud_music (local music routes)
├── memory/        # facts, vector, data_store
├── perception/    # camera, screen, vision, uivision, windows
├── skills/        # coder, browser, journal, scheduler, jobs, proactive, alerts,
│                  # assistant_features, capabilities, triggers, agent, emotion, languages
├── integrations/  # google_apis, spotify, home_assistant, phone, github
├── system/        # access, installer, hotkey
└── tests/         # pytest suite
launch-zendaya.ps1   quit-zendaya.ps1   setup-zendaya.ps1
```

---

## Setup (Windows)

Prerequisites: **Python 3.14** and a `venv` at `./venv`.

```powershell
# 1. Create the virtual environment (once)
python -m venv venv

# 2. Install dependencies + create desktop shortcuts
./setup-zendaya.ps1
#    (installs backend/requirements.txt + requirements-offline-voice.txt)

# 3. Offline TTS phonemizer (required for the offline voice)
winget install --id eSpeak-NG.eSpeak-NG -e
```

Create a `.env` in the repo root (see `.env.example`). The only required key is the
Gemini API key; the rest enable optional features:

```env
GEMINI_API_KEY=...            # required (the brain)
ELEVENLABS_API_KEY=...        # optional — enables the on-demand ElevenLabs voice
SPOTIFY_CLIENT_ID=...         # optional — Spotify skill
SPOTIFY_CLIENT_SECRET=...
HF_TOKEN=...                  # optional — pyannote (speaker features)
```

> Secrets live in `.env` (gitignored). Do **not** hardcode tokens in source.

---

## Running

- **Start:** the **Zendaya** desktop shortcut, or `./launch-zendaya.ps1` — runs the
  backend hidden via the supervisor (restarts on crash).
- **Quit:** the **Quit Zendaya** shortcut, `./quit-zendaya.ps1`, or say/type `/quit`.
- **Dev (interactive console):**
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  Push-Location backend
  & ../venv/Scripts/python.exe zendaya.py
  Pop-Location
  ```

Useful runtime commands: `/voice offline`, `/voice elevenlabs`, `/voice status`, `/quit`.

---

## Tests

```powershell
& ./venv/Scripts/python.exe -m pytest backend/tests -q -m "not slow"
# the slow real-synthesis test (downloads/loads the Coqui model):
& ./venv/Scripts/python.exe -m pytest backend/tests -m slow -q
```

---

## License

MIT — see [LICENSE](LICENSE).
