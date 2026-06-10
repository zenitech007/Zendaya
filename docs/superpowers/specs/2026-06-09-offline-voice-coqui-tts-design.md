# Offline-First Voice for Zendaya — Coqui TTS (VITS) — Design

- **Date:** 2026-06-09
- **Status:** Draft for review
- **Owner:** Zendaya
- **Topic:** Free, offline text-to-speech as Zendaya's default voice, with ElevenLabs kept as an on-demand option.

## 1. Goal

Give Zendaya a **free, offline** spoken voice using **Coqui TTS**, as the **default** voice, while keeping the existing **ElevenLabs** cloud voice available **on demand** (offline-first hybrid). The robotic `pyttsx3` engine stays only as a last-resort fallback.

Speech-in (STT) is already fully offline (`faster-whisper` + `openwakeword`) and is **out of scope** here.

## 2. Background — current state

- **TTS primary:** ElevenLabs streaming TTS in `backend/zendaya.py` (`speak_async()`), 22050 Hz PCM (`_TTS_PCM_RATE`), with a "signature" voice id. Requires `ELEVENLABS_API_KEY` + internet.
- **TTS fallback:** `pyttsx3` (Windows SAPI) — offline but robotic (`initialize_system_tts()` / `speak_system_fallback()`).
- **HUD coupling:** the PCM stream drives the HUD orb + viseme lip-sync via `_stream_pcm_playback()`, `_set_tts_gate()`, and a monotonic per-utterance id (`_new_utt_id()`). Barge-in is handled by `_TTS_STOP` / `stop_speaking()`.
- **Already installed:** `coqui-tts 0.27.5`, `torch 2.11.0+cpu`, `numpy 2.4.4` in the project venv (Python **3.14.3**).

## 3. Requirements

### Functional
- Default to an **offline Coqui voice** for all of Zendaya's speech.
- Provide a runtime switch to **ElevenLabs** and back: `/voice offline | elevenlabs | status`; the choice **persists** across restarts.
- Offline speech must drive the **HUD orb + visemes** and support **barge-in** exactly like the current ElevenLabs path.
- Graceful **fallback chain** (see §8) so Zendaya always speaks if any engine is unavailable.

### Non-functional
- **Offline after first-run:** the voice model downloads once, then runs with no internet.
- **CPU-only:** the box has no GPU (`torch.cuda.is_available() == False`). The default model must synthesize a sentence in well under ~1s.
- **Isolated & testable:** Coqui lives behind one module with a narrow interface; the change to the protected `zendaya.py` is a small, surgical hook.
- **Don't disturb shared deps:** keep `transformers 5.8.0` (needed by `airllm`, `optimum`) untouched.

## 4. Constraints & environment findings

| Item | Finding | Consequence |
|---|---|---|
| Python | 3.14.3 (venv) | Must use wheels that exist for cp314. |
| Torch | 2.11.0 **+cpu** | CPU-only → favor fast VITS, not XTTS, for the "now" voice. |
| `import TTS` | Fails: `cannot import name 'isin_mps_friendly'` (transformers 5.x removed it) | Add a runtime **shim**, not a downgrade. |
| transformers | 5.8.0, required by `airllm`/`optimum` | **Do not** downgrade; shim instead. |
| torchcodec | Not installed; `torch>=2.9` makes Coqui require it. `torchcodec 0.14.0` **has a cp314 wheel**. | `pip install torchcodec`. |
| FFmpeg | **Not on PATH**; torchcodec needs FFmpeg libs at runtime | Install FFmpeg (also needed later for XTTS reference audio). |

## 5. Chosen approach — A: in-process module + thin hook

Rationale: Coqui already lives in this venv; an in-process module is the smallest, most testable change, reuses the existing PCM/viseme pipeline untouched, and leaves a clean seam to swap the VITS model for **XTTS-v2 voice-cloning** later (the eventual "Black American" voice goal) behind the same `synth_to_pcm()` interface. (Rejected: out-of-process microservice — extra plumbing for no extra capability here; Piper — no AA-voice / XTTS path.)

## 6. Default voice

- **Model:** `tts_models/en/vctk/vits` — one fast model, ~100 selectable English speakers, **native 22050 Hz** (matches `_TTS_PCM_RATE`, no resampling), CC-BY license.
- **Speaker:** a configurable default (`VCTK_SPEAKER`, e.g. `p225`), with a short audition list tried during implementation to pick a pleasant female voice. Easily changed via config; a deeper/warmer speaker can serve as a stepping stone toward the future AA clone.

## 7. Components & interfaces

### 7.1 `backend/zendaya_offline_tts.py` (new)
- **Compat shim (idempotent), executed before `import TTS`:** if `transformers.pytorch_utils.isin_mps_friendly` is missing, inject a `torch.isin`-based equivalent.
- **Lazy singleton model:** load `tts_models/en/vctk/vits` once (first run downloads + caches; thereafter offline), guarded by a `threading.Lock`.
- **`synth_to_pcm(text: str, target_sr: int = 22050) -> bytes`:** synthesize → float32 waveform → (resample only if model SR ≠ target) → **int16 little-endian PCM** bytes. Splits long text into sentences and concatenates.
- **`warmup()` / `is_ready()`** for an optional startup pre-load.
- **Failure mode:** raise typed `OfflineTTSError`; never hard-crash the caller.
- **Config:** model id, default speaker, target sample rate.

### 7.2 Engine selector in `backend/zendaya.py` (surgical hook)
- `_VOICE_ENGINE` preference, default `"offline"`, **persisted** in `zendaya_data` (e.g. `voice_engine.json`), loaded at startup.
- In `speak_async()`:
  - `offline` → `zendaya_offline_tts.synth_to_pcm(text)` → feed bytes into the **existing** PCM feeder with a fresh `_new_utt_id()` and `_set_tts_gate(True/False)` bracket.
  - `elevenlabs` → existing ElevenLabs streaming path (unchanged).
- Reuses `_TTS_STOP` / `stop_speaking()` so **barge-in works for offline too**.

### 7.3 Switch control
- Slash command `/voice offline | elevenlabs | status` registered in the existing slash registry; backend `set_voice_engine(name)` validates + persists and returns the active engine for HUD display.

## 8. Fallback chain

- Engine = **offline**: Coqui synth/import fails → log **once** → `pyttsx3` (`speak_system_fallback`).
- Engine = **elevenlabs**: no API key / no internet / API error → **offline** Coqui → then `pyttsx3`.
- **First run, model not cached, no internet:** → `pyttsx3` with a clear one-time log instructing to run once online to cache the model.

## 9. Data flow

```
reply text
  → speak()/speak_async()
    → engine selector (_VOICE_ENGINE, default "offline")
      → zendaya_offline_tts.synth_to_pcm(text)           # 22050 Hz int16 PCM
        → _set_tts_gate(True)
        → chunked PCM feeder tagged with _new_utt_id()    # existing path
          → sounddevice output + HUD viseme/orb stream
        → _set_tts_gate(False)
   barge-in: _TTS_STOP.set() via stop_speaking()  (cuts offline + cloud alike)
```

## 10. Dependency remediation (Phase 0, one-time)

1. `pip install torchcodec` (0.14.0, cp314 wheel confirmed).
2. Install **FFmpeg** shared libs (e.g. `winget install Gyan.FFmpeg`); verify torchcodec imports.
3. Verify the `isin_mps_friendly` shim → `import TTS` succeeds (transformers stays 5.8.0).
4. Smoke test: synth one sentence with `tts_models/en/vctk/vits` → assert a 22050 Hz int16 PCM buffer is produced.

## 11. Testing strategy

`backend/tests/test_zendaya_offline_tts.py`:
- `synth_to_pcm("hello")` returns non-empty **int16 PCM @ 22050 Hz** (Coqui model **mocked** for speed).
- Long text is **sentence-split** and concatenated.
- Engine selector routes correctly and walks the **full fallback chain** (offline→pyttsx3; elevenlabs→offline→pyttsx3) with mocks.
- `/voice` command parsing + persistence round-trip.
- Barge-in (`stop_speaking`) halts the offline feeder.
- One **slow** real-synthesis integration test, `@pytest.mark.slow`, **skipped by default**.

## 12. Future work (out of scope now)

- **XTTS-v2 voice-cloning** for an African-American voice from a reference clip, dropped in behind the same `synth_to_pcm()` interface (needs FFmpeg/torchcodec — already installed in Phase 0). Expect higher CPU latency; likely paired with sentence-level pre-synthesis or kept as a non-default option.

## 13. Out of scope / YAGNI

- Changing STT (already offline).
- Streaming partial audio from VITS (not supported; sentence-level granularity is enough on CPU).
- A full HUD settings UI for voice (the `/voice` command is sufficient for now).
- Removing ElevenLabs (kept as an on-demand option).

## 14. Open risks

- **FFmpeg/torchcodec runtime** on Windows + py3.14 is the main unknown; Phase 0 validates it before any app wiring.
- **VITS speaker choice** is subjective — finalized by auditioning during implementation.
- Editing `zendaya.py` (part of an uncommitted protected WIP diff) — keep the hook minimal and review the diff carefully before any commit.
