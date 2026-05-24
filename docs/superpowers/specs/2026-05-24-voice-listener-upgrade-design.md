# Voice Listener Upgrade — Clearer, Noise-Cancelled, Faster — Design

**Date:** 2026-05-24
**Status:** Approved (pending spec review)
**Author:** Claude Opus 4.7 (with zenitech007)
**Successor to:** [2026-05-23-assistant-features-wireup-design.md](2026-05-23-assistant-features-wireup-design.md)

## Goal

Make Zendaya's voice listener feel like a modern, responsive AI assistant: cleaner audio in noisy rooms, fewer false fires from background sound, lower latency from wake → reply, and a wake-word path that aims to swap "hey jarvis" for "Zendaya" if a community model exists.

## Non-goals

- Picovoice / Porcupine. The user cannot create a Picovoice account, so `pvporcupine` stays unused (it remains installed but unreferenced).
- Custom-training an openWakeWord model from scratch (~500 voice samples). Deferred unless the community-model search comes up empty AND the user later commits to recording.
- Replacing `faster-whisper`. We're tuning it, not swapping engines.
- Speculative LLM dispatch on partial transcripts ("she replies before you finish"). Marked as a follow-up beyond this spec.
- Wholesale rewrite of the v1 listener (`backend/zendaya_voice_listener.py`). Stale, but a separate cleanup task.
- Touching the user's pre-existing uncommitted diff. As with prior specs in this repo, that diff is left alone.

## Context

Current voice listener (`backend/zendaya_voice_listener_v2.py`) maps as follows (verified by codebase scout):

- **Wake:** openWakeWord built-in `hey_jarvis`, threshold 0.5 cold / 0.72 barge-in, 5-frame smoothing (~400ms minimum reaction).
- **Verifier:** 2nd-stage Whisper pass on 1.5s pre-roll; regex matches `zendaya|jarvis|zen|…` (loose `zen` is a false-positive magnet).
- **STT:** faster-whisper, distil-small.en for English / small otherwise, int8 CPU, `beam_size=5`, lazy-loaded — first wake suffers full model load (multi-second).
- **VAD:** Silero VAD (ONNX), 30ms frames, 450ms / 900ms silence hangover.
- **Audio:** sounddevice, 16kHz mono, **opens/closes stream per utterance** (per-cycle device-init jitter).
- **Denoise:** `noisereduce` stationary spectral subtraction, **once per full utterance**.
- **AGC:** per-frame, target peak 0.70.
- **Threading:** daemon listener thread; **synchronous dispatch** — listener blocks on the entire Gemini round-trip before it can hear the next wake.
- **TTS gate:** mic stream stays open during TTS; only wake engine consulted, barge-in armed at the stricter 0.72.

Decisions captured during brainstorming:
- Wake direction: **search community openWakeWord models for "Zendaya"** first; fall back to a **tightened "hey jarvis"** if nothing exists.
- Noise cancellation: **DeepFilterNet** (ML-based, ~50-100MB model, ~1-3% CPU, real-time per-frame) replacing per-utterance stationary `noisereduce`.
- Response speed: **safe wins + async dispatch + pre-EOS streaming transcription as a stretch goal**. Speculative dispatch on partial transcripts is explicitly deferred.

## Architecture

No new top-level module. All upgrades land in the existing `backend/zendaya_voice_listener_v2.py` and `backend/voice/*.py` helpers.

| File | Action | Responsibility |
|---|---|---|
| `backend/zendaya_voice_listener_v2.py` | Modify | Persistent audio stream; Whisper preload at startup; tightened thresholds; ambient-RMS floor gate; async dispatch worker thread; verifier-skip on high-confidence wakes; route DFN output to STT only; stretch: pre-EOS streaming transcription |
| `backend/voice/denoise.py` | Modify | Add `DeepFilterDenoiser` class implementing the same `denoise(audio, sr) -> audio` interface as existing `Denoiser`. Module-level factory `make_denoiser()` picks DFN if importable, falls back to `Denoiser` |
| `backend/voice/wake.py` | Modify | Threshold tuning (0.5 → 0.6 cold; add 0.85 verifier-skip threshold); tightened verifier regex (no loose `zen`); env-driven model name; load community `zendaya_wake.onnx` if present |
| `backend/voice/zendaya_wake.onnx` | Created externally if community model is found | Drop-in openWakeWord ONNX model. NOT committed (binary, regenerable from upstream) |
| `pyproject.toml` | Modify | Add `deepfilternet` |
| `backend/tests/test_voice_listener_v2.py` | Create | Unit tests for denoiser factory, verifier regex, ambient floor gate, dispatch queue bounding, worker TTS gate, verifier-skip threshold; one integration smoke test with mocked `sd.InputStream` |

**Wake-vs-STT denoise split:** Wake detector consumes **raw** audio (openWakeWord is trained on noisy speech; aggressive filtering can mute faint wakes). DeepFilterNet output feeds **only** the STT path. This is the standard pattern.

## Pipeline data flow

```
Mic → sounddevice InputStream (persistent, opened ONCE at startup)
      │  16kHz mono int16, 30ms frames (480 samples)
      ▼
   audio_queue → Frame consumer loop (zendaya-voice-v2 thread)
                 │
                 ├─► AGC (per-frame, unchanged)
                 │
                 ├─► Ambient-RMS floor gate                                  [NEW]
                 │     500ms rolling RMS; skip wake-detection on this frame
                 │     when room is below floor AND TTS isn't speaking.
                 │
                 ├─► WakeEngine (openWakeWord — raw audio, NOT denoised)
                 │     score ≥ 0.6  → enter recording sub-mode               [tightened]
                 │     score ≥ 0.85 → skip 2nd-stage Whisper verifier        [NEW]
                 │
                 ├─► Pre-roll buffer (1.5s ring) for borderline verifier
                 │
                 └─► Recording (until Silero VAD EOS or 15s cap)
                       │  Silence hangover: 450ms / 700ms (tightened from 450/900)
                       ▼
                    Utterance buffer
                       │
                       ▼
                  DeepFilterDenoiser                                          [NEW]
                       │  Per-utterance call now; per-frame is a stretch
                       ▼
                  faster-whisper (preloaded at startup, beam_size=1)         [tightened]
                       │
                       ▼
                  Tightened verifier regex                                    [tightened]
                       │  hey_jarvis model → \b(jarvis|zendaya)\b
                       │  zendaya model    → \bzendaya\b
                       ▼
              ┌──── dispatch_queue (bounded, max 2 pending) ────┐             [NEW]
              │  worker thread (zendaya-voice-dispatch)          │
              │  calls z.handle_user_command(text)               │
              │  while listener thread immediately resumes wake  │
              └──────────────────────────────────────────────────┘
```

## Wake-word strategy

### Step 1: Community model search (runs as the implementation plan's first task)

Search HuggingFace and known openWakeWord community repos for any model labelled `zendaya`, `zen-daya`, or close phonetic variants. Two outcomes:

- **Hit:** download the `.onnx` to `backend/voice/zendaya_wake.onnx`. Set `ZENDAYA_WAKE_MODEL=zendaya` as the new default. Done.
- **Miss (likely — "Zendaya" is unusual):** stay on `hey_jarvis`. The tightening below makes it noticeably less twitchy.

### Step 2: Sensitivity tuning (applies regardless of model)

| Knob | Current | New | Why |
|---|---|---|---|
| Cold wake threshold | 0.5 | **0.6** | Less twitchy on background noise |
| Barge-in threshold | 0.72 | 0.72 | Already strict; unchanged |
| Smoothing window | 5 frames | 5 frames | Debounces single-frame spikes; unchanged |
| Cooldown | 1.5s | 1.5s | Unchanged |
| Verifier-skip threshold | (none) | **0.85** | High-confidence wakes skip the 200-600ms verifier pass |

### Step 3: Tightened 2nd-stage verifier

Replace the loose `zendaya|jarvis|zen|…` substring match with model-aware word-boundary regex:
- `hey_jarvis` → `\b(jarvis|zendaya)\b`
- `zendaya` → `\bzendaya\b`

Drops false confirmations on "zenith", "frozen", "lens", etc.

### Step 4: Ambient-RMS floor gate

Track a 500ms rolling RMS. When TTS isn't speaking AND room RMS < env `ZENDAYA_AMBIENT_FLOOR` (default 0.005), skip wake-engine call on this frame. Saves ~3-5% CPU in quiet rooms and eliminates a class of barely-audible false fires.

When ambient rises back above the floor, wake detection resumes immediately (openWakeWord is stateless across short gaps).

## STT optimisations

| Change | Why | Where |
|---|---|---|
| Preload Whisper at `start_voice_listener()` | First wake no longer cold-loads | `start_voice_listener()` calls `_init_whisper()` synchronously before returning |
| `beam_size=1` | Commands are short; beam search adds 100-300ms with negligible accuracy gain | [v2.py:236](../../../backend/zendaya_voice_listener_v2.py) |
| Skip verifier when wake score ≥ 0.85 | Saves 200-600ms on confident wakes | `_run_listener_session` |
| Silence hangover 450/700ms | Was 450/900ms; the long branch was over-conservative | [v2.py:87-88](../../../backend/zendaya_voice_listener_v2.py) |
| Persistent audio stream | Eliminates per-cycle ~50-100ms device-init jitter | `sd.InputStream` lifted into module scope, opened once at startup |
| `DeepFilterDenoiser` replaces per-utterance `noisereduce` call | Better quality, especially on non-stationary noise (typing, family chatter) | New class in `voice/denoise.py`; factory selects DFN if available, falls back to existing `Denoiser` |

**Expected combined latency reduction (warm path):** ~30-50%. Current rough baseline ≈ 1.2-1.8s (wake → reply start). Target ≈ 0.7-1.0s.

**Async dispatch (architectural):** listener thread enqueues `(text, timestamp)` on a bounded `queue.Queue` (max 2 pending) and immediately resumes wake detection. A dedicated worker thread (`zendaya-voice-dispatch`) consumes the queue and calls `z.handle_user_command(text)`. Old pending commands are dropped (oldest-first) when the queue overflows — intentional, since stale commands lose relevance fast.

### Stretch goal — pre-EOS streaming transcription

faster-whisper supports passing a streamable audio source; instead of waiting for Silero VAD to declare end-of-speech, kick off transcription after ~1 second of audio. By the time EOS fires, the transcript is mostly ready. Saves ~200-400ms.

**Decision rule:** implement only if it lands in 1-2 plan tasks without destabilising end-of-utterance accuracy. If the partial-transcript pattern introduces flakiness in any of the existing tests or smoke checks, defer to a follow-up spec. The plan flags this explicitly.

**Speculative dispatch on stable prefixes** ("she replies mid-sentence") is **out of scope** for this spec under any condition.

## Error handling

Every optional piece degrades gracefully. Pattern matches the existing `_VMEM_READY` / `_CODER_READY` / `_AAF_READY` style elsewhere in the codebase.

| Failure | Behavior |
|---|---|
| `deepfilternet` import fails | Log once at startup. Factory returns existing `Denoiser`. Listener fully functional, just with less aggressive denoise. |
| DeepFilterNet model first-run download/init > 30s | Abort, log warning, fall back to `Denoiser`. |
| Community `zendaya_wake.onnx` file present but fails to load | Log warning, fall back to `hey_jarvis`. |
| Whisper preload fails | Log, listener still starts. First wake retries via the existing lazy-load path. |
| Audio stream errors mid-session (mic unplugged, device change) | Catch `sounddevice.PortAudioError`, log, close stream, sleep 2s, re-open. After 3 failures in 60s, revert to per-session open/close and log "audio stream unstable, reverting to per-session opens". |
| Dispatch queue full (3rd command arrives while 2 pending) | Drop oldest pending command, log `(voice v2: dropped stale command — too many pending)`. New command still processes. |
| Worker thread crash inside `handle_user_command` | Caught, logged with traceback, worker thread auto-restarted. Listener thread untouched. |
| `_TTS_SPEAKING` event stuck "on" (TTS module crash) | Worker waits up to 30s on the event; if it times out, dispatches anyway with a log. Prevents permanent deadlock. |
| `ZENDAYA_AMBIENT_FLOOR` env value unparseable | Log warning, use default 0.005. |

Every degrade prints one informative line at startup so the user can grep logs to see which optional pieces loaded.

## Testing strategy

**New file:** `backend/tests/test_voice_listener_v2.py`. Reuses the existing `backend/tests/conftest.py` fixtures (the `sys.path` injection that makes `backend/` importable).

### Unit (no real audio)

1. **Denoiser factory** — table-driven: with `deepfilternet` importable, returns `DeepFilterDenoiser`; raises `ImportError`, returns `Denoiser`. Both expose `denoise(audio, sr) -> audio`.
2. **Wake verifier regex** — model-aware match table including the regression cases the old loose regex would have failed: `("hey_jarvis", "okay jarvis what time is it", True)`, `("hey_jarvis", "what's the frozen lake forecast", False)`, `("zendaya", "hey zendaya open spotify", True)`, `("zendaya", "the zenith is bright", False)`.
3. **Ambient floor gate** — synthetic frame stream (silence → speech-level → silence). With floor 0.005, mock wake engine call count matches expected pass-through frames ±1.
4. **Dispatch queue bounding** — fill past cap, assert oldest items dropped + log line recorded. Worker FIFO. Worker exception doesn't stop subsequent items.
5. **Worker TTS gate** — set `_TTS_SPEAKING`, enqueue, assert worker doesn't dispatch until event clears. Simulate stuck event, assert dispatch fires anyway after 30s timeout.
6. **Verifier-skip threshold** — mock wake at 0.9 → `_init_whisper` NOT called for verifier. Mock wake at 0.6 → verifier runs.

### Integration smoke (with mocked sounddevice)

7. **End-to-end happy path** — mock `sd.InputStream` emits a known WAV file frame-by-frame: silence → wake-word audio → command audio → silence. Assert wake fires, transcript captured, dispatch queue receives expected text, worker calls a mock `handle_user_command`.

### Not tested

- Real DeepFilterNet denoise quality (audio quality is subjective; manual ear check).
- Real wake-word accuracy on the user's voice (depends on mic + room — manual).
- Real Whisper transcription accuracy.

### Manual verification checklist

- [ ] Start the assistant. Whisper preload visible in startup logs (no cold-load latency on first wake).
- [ ] Say "hey jarvis, what time is it" — time-to-reply feels noticeably faster than before the change.
- [ ] Background TV at moderate volume — wake + command — transcript is clean (no TV bleed words in the transcription).
- [ ] Issue two wake commands in quick succession — second queues and runs after first finishes (async dispatch).
- [ ] Try "frozen lake" or "the zenith is bright" — no false wake.
- [ ] Whisper a wake command quietly — still triggers if above ambient floor.
- [ ] Stay silent in a quiet room for 30s — zero false wakes (ambient floor gate active).
- [ ] Unplug mic mid-session, plug back in within 5s — listener recovers automatically (logged).

## Done criteria

- `deepfilternet` listed in `pyproject.toml` deps; importable in env.
- `DeepFilterDenoiser` class + `make_denoiser()` factory exist in `backend/voice/denoise.py`; factory selects DFN when available, `Denoiser` when not.
- `backend/voice/wake.py` thresholds updated (0.5→0.6 cold, +0.85 verifier-skip); verifier regex tightened to model-aware word-boundary form.
- `backend/zendaya_voice_listener_v2.py` has: persistent `sd.InputStream`, Whisper preload in `start_voice_listener()`, `beam_size=1`, verifier-skip on high-confidence wakes, tightened silence hangover, ambient-RMS floor gate, dispatch worker thread + bounded queue.
- `backend/tests/test_voice_listener_v2.py` exists; full pytest suite passes (both this file's tests AND the prior 56 AAF tests).
- Manual verification checklist passes on user's machine.
- Streaming pre-EOS transcription is either implemented (stretch goal hit) or explicitly noted as deferred in the final commit message.

## Risks and unknowns

| Risk | Mitigation |
|---|---|
| DeepFilterNet PyTorch dep collides with the project's existing torch / model deps | Pin a compatible version range; if conflicts, document and fall back to RNNoise (still better than current stationary noisereduce) |
| Community openWakeWord model for "Zendaya" doesn't exist | Expected outcome. Spec proceeds with tightened `hey_jarvis`. Custom-training documented as future work |
| Persistent audio stream stays open during TTS — risk of echo feedback if speakers leak into mic | Existing TTS gate already handles this (wake-only mode during TTS). New persistent stream changes nothing about that gate |
| Async dispatch reorders commands (user expects strict order) | Queue is FIFO; worker is single-threaded. Order preserved. Only drop policy is oldest-first when over-capacity |
| Pre-EOS streaming destabilises end-of-utterance transcript accuracy | Stretch goal only; if any test or smoke flake occurs, the implementation reverts to current EOS-first transcription and notes the defer in the commit message |
| User's pre-existing 4,400-line uncommitted diff overrides v2 listener changes when it eventually lands | Same caveat as AAF wire-up. Voice changes commit against HEAD; user re-stitches when the pre-existing diff is resolved. See [[project-uncommitted-diff]]. |
| Worker thread leaks if shutdown path doesn't join it | Add a `stop_voice_listener()` exit handler that signals the worker via a sentinel and joins with a 2s timeout |

## Deferred / future work

- Speculative LLM dispatch on stable partial transcripts ("she starts replying mid-sentence").
- Custom-trained openWakeWord "Zendaya" model from user voice recordings.
- Mic device hot-swap UI (let the user pick which input device to use without env vars).
- Smarter ambient floor — currently a static value; could auto-calibrate by sampling the room for 5s at startup.
- Multi-microphone array support / beamforming (out of scope for a single-mic laptop setup).
- v1 listener cleanup (`backend/zendaya_voice_listener.py`) — separate task.
