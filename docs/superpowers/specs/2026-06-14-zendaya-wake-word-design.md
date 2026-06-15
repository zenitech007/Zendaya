# Custom "Zendaya" / "Zen" Wake Words — Design

- **Date:** 2026-06-14
- **Status:** Draft for review
- **Topic:** Replace the `hey_jarvis` wake word with custom "Zendaya" (primary) and "Zen" (secondary) openWakeWord models.

## 1. Goal

Let the assistant wake on **"Zendaya"** (reliable primary) and **"Zen"** (secondary, tamed), instead of `hey_jarvis`. Stay free + offline at runtime.

## 2. Background — current two-stage wake system

- **Stage 1 (acoustic):** `backend/voice/wake.py` `WakeEngine` runs an openWakeWord ONNX model (`hey_jarvis`) on every 80 ms / 1280-sample frame; a 5-frame moving average ≥ threshold fires (with a 1.5 s cooldown). Model + threshold are env-configurable: `ZENDAYA_WAKE_MODEL`, `ZENDAYA_WAKE_THRESHOLD`. The listeners (`voice/listener.py`, `voice/listener_v2.py`) build the engine.
- **Stage 2 (verify):** a 1.2 s Whisper pre-roll transcript is matched against a regex. **The verifier already supports "zendaya"** — `VERIFY_RE_ZENDAYA` (with mishear variants: zendia/zendaia/zen daya/sendaya/sandaya) and `verifier_passes_for_model("zendaya", …)`.
- **Why it was on `hey_jarvis`:** openWakeWord ships only pretrained models (hey_jarvis, alexa, …); there is no pretrained "Zendaya"/"Zen" acoustic model. Stage 1 was the blocker, not Stage 2.

## 3. Decisions (from brainstorming)

- **Engine:** custom openWakeWord `.onnx` models (free, offline, reuses the existing engine + verifier).
- **Training:** openWakeWord's **automatic-training Google Colab** (free GPU). Pure **synthetic** data (no user voice recording).
- **Scope:** both words; **"Zendaya" primary**, **"Zen" tamed** (higher Stage-1 threshold + Stage-2 verify) — "Zen" is a single short syllable and will false-fire more.
- **Division of labor:** I generate a synthetic validation clip + the Colab guide + all the integration code/tests/docs; **you run the Colab** (download `zendaya.onnx`, `zen.onnx`) and do the one live mic test.

## 4. Requirements

**Functional**
- Default wake = bundled `zendaya.onnx` (+ `zen.onnx`); saying either wakes the assistant.
- Per-model Stage-1 thresholds (Zendaya ≈ 0.5, Zen ≈ 0.7).
- Stage-2 verifier accepts "zendaya" (existing) and a bare "zen", chosen by which model fired.
- Runtime override via `ZENDAYA_WAKE_MODEL` (comma-separated paths or a builtin name) and `ZENDAYA_WAKE_THRESHOLD` preserved.

**Non-functional**
- Free + offline at runtime (no SaaS/account). Training is a one-time free Colab GPU step.
- Graceful fallback: missing/broken model → clear log, assistant keeps running.
- Mic-free verifiability: a synthesized "Zendaya" clip can validate the trained model end-to-end (since no mic in CI).

## 5. Constraints / realities

| Item | Reality | Consequence |
|---|---|---|
| Hardware | CPU-only (no GPU) | Train on free Colab GPU, not locally. |
| openWakeWord custom model | `Model(wakeword_models=["/path/x.onnx"])` accepts file paths | Single "Zendaya" is nearly drop-in; dual-model needs engine work. |
| "Zen" | one short syllable | higher false-alarm rate; tamed via threshold + verify; accepted risk. |
| "zen" ⊂ "zendaya" | substring | verifier model-routing must check "zendaya" before "zen". |

## 6. Components

### 6.1 Models — `backend/voice/models/`
Bundled `zendaya.onnx` and `zen.onnx` (small ONNX, committed). New default for the engine.

### 6.2 `voice/wake.py` — `WakeEngine`
- **Multi-model load:** accept a list of model **paths** (default: the two bundled files). Resolve `ZENDAYA_WAKE_MODEL` as comma-separated paths, else a builtin name (back-compat).
- **Fired-model tracking:** `push()` keeps returning `bool`, but also sets `self.last_fired_model` (the model whose smoothed score crossed its threshold) so the caller picks the right Stage-2 verifier.
- **Per-model thresholds:** a `{model: threshold}` map; default Zendaya 0.5, Zen 0.7; `ZENDAYA_WAKE_THRESHOLD` overrides the global default. `barge_threshold` stays stricter.
- **Predict:** `_OWWModel.predict()` returns `{model_key: score}`; smooth per-model; fire if any model's smoothed score ≥ its threshold (record which).

### 6.3 `voice/wake.py` — verifier
- Keep `VERIFY_RE_ZENDAYA`. Add `VERIFY_RE_ZEN = re.compile(r"\bzen\b", IGNORECASE)`.
- `verifier_passes_for_model(model_name, transcript)`: if `"zendaya" in name` → `VERIFY_RE_ZENDAYA`; elif `"zen" in name` → `VERIFY_RE_ZEN`; else fall back to the combined regex. (Order matters because "zen" ⊂ "zendaya".)
- Homophone note: `\bzen\b` rejects "zenith"/"frozen"/"present" (no word boundary) but *will* match a bare "zen" inside "zen garden"; combined with the listener's start-anchored wake regex + the higher Stage-1 threshold this is the accepted residual "Zen" risk.

### 6.4 Listeners — `voice/listener.py`, `voice/listener_v2.py`
- Default model(s) → the bundled custom models instead of `hey_jarvis`.
- On a Stage-1 fire, pass `engine.last_fired_model` to `verifier_passes_for_model(...)`.
- Bare-wake acknowledgements unchanged.

### 6.5 Training guide (mine)
- `docs/superpowers/guides/wake-training-colab.md` — precise, words-pre-filled, click-through guide for openWakeWord's automatic training Colab (run once per word; tips: more samples/epochs + higher deploy threshold for "Zen"). Output: `zendaya.onnx`, `zen.onnx`.
- The synthetic **validation clip** is generated inside the smoke test itself via the existing `voice.offline_tts.synth_to_pcm("Zendaya")` (resampled to 16 kHz) — no separate script needed (the old `scripts/` dir was removed in the cleanup).

## 7. Data flow

```
mic frame → WakeEngine([zendaya.onnx, zen.onnx])
          → per-model smoothed score ≥ per-model threshold → fire + last_fired_model
          → record 1.2 s pre-roll → Whisper transcript
          → verifier_passes_for_model(last_fired_model, transcript)
          → wake confirmed → handle command
```

## 8. Testing

`backend/tests/test_wake.py`:
- **Verifier:** `verifier_passes_for_model("zendaya", t)` accepts "zendaya"/mishears; `("zen", t)` accepts a bare "zen" and **rejects** "zenith"/"frozen"/"present". Model-routing order ("zendaya" before "zen").
- **Engine config:** multi-path parsing of `ZENDAYA_WAKE_MODEL`; per-model threshold map; `last_fired_model` set on a simulated fire (model + scores mocked — no real ONNX needed).
- **Mic-free smoke (`@pytest.mark.slow`, skip if model/deps absent):** synthesize a "Zendaya" clip with Coqui, feed 80 ms frames through the real `WakeEngine` loaded with `zendaya.onnx`, assert it fires. Self-skips if `backend/voice/models/zendaya.onnx` isn't present yet.

## 9. Division of labor

| Step | Who |
|---|---|
| Engine multi-model + verifier + listener wiring + tests + docs | **Me** (now) |
| Synthetic validation clip generator | **Me** |
| Colab training guide | **Me** |
| Run Colab, download `zendaya.onnx` / `zen.onnx` into `backend/voice/models/` | **You** |
| Run the mic-free smoke test + one live "Zendaya" test | **Me (smoke) / You (live)** |

## 10. Out of scope / YAGNI

- Recording the user's own voice (deferred optional enhancement).
- Picovoice/Porcupine and transcript-only approaches (rejected in brainstorming).
- Multi-language wake words; per-user speaker-gated wake.

## 11. Open risks

- **"Zen" false fires** — inherent to a 1-syllable wake word; mitigated, not eliminated. If too twitchy, raise its threshold or drop it.
- **Colab pipeline drift** — openWakeWord's notebook may change; the guide may need a tweak when you run it.
- **Trained-model quality** — synthetic-only can underperform for unusual accents/mics; optional user-voice data is the fallback.
