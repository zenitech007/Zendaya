# Pack A — Conversation Flow — Design

- **Date:** 2026-06-14
- **Status:** Draft for review
- **Topic:** Make Zendaya's turn-taking feel like a real conversation: acoustic barge-in, streaming TTS, backchannels, follow-up polish.

## 1. Goal

Smooth the walkie-talkie feel of the voice loop with four upgrades, in safest→headline order:
1. **Backchannels** — verbal "thinking" cues during long tasks (no dead air).
2. **Follow-up window polish** — make the existing 20 s window configurable + add a "still-listening" cue.
3. **Acoustic barge-in** — interrupt by *talking over her*, not only by re-saying the wake word.
4. **Streaming sentence-by-sentence TTS** — first audio in <1 s instead of generate-then-speak.

Stay offline-first and dependency-light (no new fragile native deps).

## 2. Background — what already exists

`backend/voice/listener_v2.py` `_run_listener_session()` is a single-thread frame loop with three modes:
- **TTS playing** (`_TTS_SPEAKING.is_set()`): **only** the wake engine listens, with the stricter `barge_threshold` (0.72). A wake fire → `_stop_tts()` → record. So **today you must say "Zendaya" to interrupt.**
- **Follow-up window** (`(now - _last_dispatch_ts) < FOLLOW_UP_S`, currently **20 s**): VAD-only activation — already conversational for follow-ups. ✅
- **Cold path**: ambient-floor gate + wake-word gated.

Supporting pieces already present: `_AmbientGate` (rolling noise floor + `below_floor()`), Silero VAD (`_VAD.is_speech(frame)`), `_stop_tts()`, `_drain_queue()`, `_record_utterance()`, the async `_DispatchQueue`. The reply→speak path: dispatch → `zendaya.handle_user_command` → `send_response` → `speak_async` → `voice.offline_tts.synth_to_pcm(full_text)` → `_stream_pcm_playback`. `_stream_pcm_playback` computes output RMS and pushes `set_amplitude`/visemes; `_TTS_STOP` already cuts playback for barge-in.

## 3. Decisions (from brainstorming)

- **Barge-in echo handling = Approach A (reference/running-baseline gate), self-calibrating, no new deps.** The wake-word barge stays as a reliable backstop ("Zendaya"/stop-word always interrupts).
- Audio setup is **both speakers and headphones**, so the gate must self-calibrate and offer a sensitivity toggle.
- Follow-up window already exists → polish only.

## 4. Components

### 4.1 Backchannels (`voice/backchannel.py`, new) — effort S
- A small set of **pre-rendered** PCM clips ("mm-hm", "one sec", "still on it") synthesized once on first use via `offline_tts.synth_to_pcm` and cached to `zendaya_data/backchannels/` (so zero runtime latency).
- `maybe_backchannel()` plays one clip via the existing audio path **only when** the current dispatched handler has run longer than `BACKCHANNEL_AFTER_S` (default 3 s) and no real TTS is active; rate-limited (min gap), never stacks, instantly interruptible (respects `_TTS_STOP`/barge).
- **Single chokepoint:** hooked in `_start_dispatch_worker` (the one place every command handler runs). When a handler starts, arm a one-shot `threading.Timer(BACKCHANNEL_AFTER_S, maybe_backchannel)`; cancel it when the handler returns. No per-skill instrumentation needed.
- Toggle: `ZENDAYA_BACKCHANNEL` = `on` (default) / `off`.

### 4.2 Follow-up window polish — effort S
- Replace the hardcoded `FOLLOW_UP_S = 20.0` with `ZENDAYA_FOLLOWUP_S` (default tuned to **10 s** — 20 s over-captures ambient chatter).
- On entering the follow-up window, emit a subtle **"still-listening" cue**: a short soft tone clip (pre-rendered) and `_set_state("listening")` so any future surface shows it. Cue is one-shot per window, toggle `ZENDAYA_FOLLOWUP_CUE` = `on`/`off`.

### 4.3 Acoustic barge-in — effort M
- New `_BargeDetector` (in `listener_v2.py`) used **only while TTS plays**. Per frame it decides "is the user talking over her?" from three signals:
  1. **Silero VAD** says speech on the frame.
  2. **Energy spike**: frame RMS exceeds a **rolling echo-baseline** (an EMA/percentile of recent during-TTS mic energy, which naturally rises to include her own echo on speakers) by `ZENDAYA_BARGE_MARGIN` (sensitivity; default tuned).
  3. **Sustained**: the above holds for `BARGE_TRIGGER_FRAMES` consecutive frames (avoids momentary echo blips).
  On trigger → same path the wake-barge uses today (`_stop_tts()`, wait for gate clear, `_drain_queue`, `_set_state("listening")`, drop into record).
- Self-calibration means: headphones → baseline ≈ ambient (low) → easy to exceed; speakers → baseline ≈ her echo (high) → only louder user speech exceeds. No per-device tuning required, but `ZENDAYA_BARGE_MARGIN` lets the user dial it.
- **Mode env** `ZENDAYA_BARGE_MODE`:
  - `acoustic` (default): run the `_BargeDetector` **and** the existing wake-engine barge in parallel (either can fire).
  - `wake`: today's behavior (wake/stop-word only).
  - `off`: no barge (must wait for her to finish).
- The `tts_on` branch of the loop is the only edit: add the detector path alongside the existing wake push, gated by mode.

### 4.4 Streaming sentence-by-sentence TTS — effort M
- Add a streaming speak path: as `gemini_reply` yields tokens, accumulate into sentences (`offline_tts._split_sentences` on the growing buffer); when a sentence completes, **enqueue it for synthesis+playback** while generation continues. A small `SentencePlayer` runs `synth_to_pcm(sentence)` → `_stream_pcm_playback` per sentence, in order, on the TTS thread.
- **Flushable**: between sentences it checks `_TTS_STOP`; a barge-in flushes the queued/pending sentences immediately (reuses `_stop_tts` + `_TTS_STOP`). The viseme/amplitude pipeline is fed per-sentence as today.
- Wiring: `send_response` (voice mode) calls a new `speak_stream(text_or_generator)`; when the reply is produced by a streaming `gemini_reply`, pass the generator; otherwise fall back to the current whole-string `speak_async`. ElevenLabs path unchanged (it already streams).
- **Dependency note:** requires `gemini_reply` to expose a token stream (google-genai `generate_content_stream`). If it's currently whole-reply, this component adds the streaming variant behind a flag and keeps the non-streaming path as fallback.

## 5. Data flow (barge-in + streaming)

```
reply text/stream → speak_stream() → per sentence: synth_to_pcm → _stream_pcm_playback
                                                   ↳ set_amplitude / visemes (echo reference)
mic frame loop (TTS on):
   wake.push(barge_in=True)  ── fires ─┐
   _BargeDetector(frame): VAD & energy>echo_baseline+margin & sustained ─┐
                                                                          ├─► _stop_tts() → flush → record
```

## 6. Components & interfaces (isolation)

- `voice/backchannel.py` — `prime()`, `maybe_backchannel(label)`, `play_cue(name)`; owns the clip cache. No knowledge of the loop internals.
- `listener_v2._BargeDetector` — `observe(frame, tts_amplitude) -> bool`; pure decision unit, unit-testable with synthetic frames.
- `voice/offline_tts` (or a new `voice/sentence_player.py`) — `speak_stream(source)`; consumes a string or a text generator, drives per-sentence synth + the existing playback, flushes on stop.
- `listener_v2` env knobs: `ZENDAYA_BARGE_MODE`, `ZENDAYA_BARGE_MARGIN`, `ZENDAYA_FOLLOWUP_S`, `ZENDAYA_FOLLOWUP_CUE`, `ZENDAYA_BACKCHANNEL`.

## 7. Error handling

- Backchannel/cue synth failure → silently skip (never block the loop).
- `_BargeDetector` exceptions → treat as "no barge" (fail-safe: don't interrupt spuriously); the wake-barge backstop remains.
- Streaming TTS: a sentence synth failure → log + speak the remaining text via the fallback whole-string path; barge mid-stream must always cleanly flush (no orphaned audio).
- All new behavior is env-toggleable so it can be disabled without code changes if it misbehaves.

## 8. Testing

`backend/tests/test_conversation_flow.py`:
- **`_BargeDetector`**: feed synthetic frame energies + VAD stub — (a) headphone case (low baseline) barges on user speech; (b) speaker case (high echo baseline) does NOT barge on echo-level energy but DOES on a sustained louder spike; (c) momentary blip (< sustained frames) does not barge; (d) margin/sensitivity respected.
- **Mode parsing**: `ZENDAYA_BARGE_MODE` acoustic/wake/off selects the right paths.
- **Backchannel gating**: plays only after the duration threshold, rate-limited, no-op when toggled off, skips when TTS active.
- **Follow-up config**: `ZENDAYA_FOLLOWUP_S` honored; cue one-shot.
- **SentencePlayer**: synthesizes sentences in order; `_TTS_STOP` mid-stream flushes the remainder (mock synth); falls back to whole-string on a synth error.
Hot-loop integration (the `tts_on` edit) gets an `ast.parse` check + the full suite + a manual live mic test by the user (talk over her on speakers and on headphones).

## 9. Out of scope / YAGNI

- True WebRTC/speex AEC (Approach B) — deferred; the self-calibrating gate + wake/stop-word backstop is enough and dependency-safe.
- Speaker ID, multilingual auto-switch, XTTS voice clone (separate features from the menu).
- Any GUI cue (headless) — the "still-listening" cue is audio + state only.

## 10. Open risks

- **Speaker-case barge tuning**: the self-calibrating baseline + margin should suppress self-trigger, but loud speakers near the mic are the hard case; the `wake`/`off` modes + `ZENDAYA_BARGE_MARGIN` are the escape hatches, and only a live mic test confirms the defaults.
- **gemini_reply streaming**: if not already streaming, the streaming-TTS component is larger (adds a streaming generation path); the plan will confirm and scope it, with the non-streaming fallback always available.
