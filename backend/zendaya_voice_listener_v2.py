"""
zendaya_voice_listener_v2.py
============================
JARVIS-grade voice listener. Drop-in replacement for zendaya_voice_listener.

Public API (unchanged, must stay stable):
  start_voice_listener()      -> threading.Thread
  set_tts_speaking(speaking)  -> None
  pause_listening()           -> None
  resume_listening()          -> None
  _transcribe(audio_int16)    -> str            (used by zendaya_hotkey)
  diagnostics()               -> str

Pipeline:
  mic 16k int16
    └─► AGC ─► DeepFilterNet denoise (passthrough if unavailable)
           └─► ring buffer (1.5 s pre-roll)
                  ├─► Silero VAD (30 ms frames, ONNX) — speech gating + endpointing
                  └─► openWakeWord (hey_jarvis) with 5-frame smoothing + cooldown
                         └─► STAGE 2: Whisper verifier on 1.2 s pre-roll
                                └─► record until trailing silence (dynamic 0.45–0.9 s)
                                       └─► faster-whisper distil-small.en (int8)
                                              └─► stack-filter hallucinations
                                                     └─► handle_user_command

While TTS is speaking the mic stays open but is routed ONLY to the wake engine
(stricter `barge_threshold`). A wake fire during TTS calls
`zendaya.stop_speaking()` and immediately drops into the record path.
"""
from __future__ import annotations

import io
import os
import queue
import random
import re
import threading
import time
import wave
from collections import deque
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
    _SD_READY = True
    _SD_ERR = ""
except Exception as e:
    _SD_READY = False
    _SD_ERR = str(e)

try:
    import speech_recognition as sr
    _SR_READY = True
except Exception:
    _SR_READY = False

# Whisper backend (faster-whisper preferred, openai-whisper fallback)
_WHISPER_BACKEND: Optional[str] = None
_WHISPER_MODEL = None
_WHISPER_MODEL_NAME: Optional[str] = None
try:
    from faster_whisper import WhisperModel  # type: ignore
    _WHISPER_BACKEND = "faster"
except Exception:
    try:
        import whisper  # type: ignore
        _WHISPER_BACKEND = "openai"
    except Exception:
        _WHISPER_BACKEND = None

from voice.agc import AGC
from voice.denoise import Denoiser
from voice.vad_silero import SileroVAD
from voice.wake import WakeEngine, verifier_passes

# -----------------------
# Config
# -----------------------
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 30                       # 480 samples — Silero accepts, our internal unit
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
ROLLING_BUFFER_S = 1.5              # pre-roll for record + Whisper verifier
MAX_UTTERANCE_S = 15.0
SHORT_SILENCE_END_S = 0.45          # end-of-turn when last partial looks complete
LONG_SILENCE_END_S = 0.90           # end-of-turn when partial seems mid-sentence
FOLLOW_UP_S = 20.0                  # within this after a dispatch, skip the wake gate
MIN_UTTERANCE_S = 0.5
VAD_TRIGGER_FRAMES = 4              # ~120 ms of speech to confirm

# Hallucination stack-filter — Whisper internals + static set
WHISPER_NO_SPEECH_MAX = 0.6
WHISPER_AVG_LOGPROB_MIN = -1.0

HALLUCINATIONS = {
    "thank you.", "thank you", "thanks.", "thanks",
    "thanks for watching.", "thanks for watching",
    "thank you for watching.", "thank you for watching",
    "please subscribe.", "please subscribe", "subscribe.", "subscribe",
    "bye.", "bye", "you", "you.", "yeah.", "yeah", "okay.", "ok.",
    ".", "?", "!", "...", "uh.", "um.", "uh", "um", "mm-hmm.", "mm-hmm",
    "[music]", "[music playing]", "music playing", "music",
    "[applause]", "applause",
}

_REPETITION_RE = re.compile(
    r"\b([\w\s'.,-]{3,40}?)([\s,.]+\1\b){2,}",
    re.IGNORECASE,
)

_WAKE_ECHO_RE = re.compile(
    r"^\s*(?:hey|yo|ok|okay)?\s*"
    r"(?:zendaya|zendia|zenday|zen\s*day|sandeya|sundae|send\s*aya|"
    r"send\s*i\s*uh|sin\s*day|jarvis|zander|zen)\b[\s,.\-!?]*",
    re.IGNORECASE,
)

_BARE_WAKE_ACKS = ["Yes?", "I'm listening.", "Go ahead.", "What's up?"]

# -----------------------
# State
# -----------------------
_LISTENING_ENABLED = True
_TTS_SPEAKING = threading.Event()
_handle_command: Optional[Callable[[str], None]] = None
_send_response: Optional[Callable[[str], None]] = None
_AUDIO_Q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=400)
_last_dispatch_ts: float = 0.0

_AGC = AGC()
_DENOISER: Optional[Denoiser] = None  # lazy
_VAD: Optional[SileroVAD] = None      # lazy
_WAKE: Optional[WakeEngine] = None    # lazy


def set_tts_speaking(speaking: bool) -> None:
    if speaking:
        _TTS_SPEAKING.set()
    else:
        _TTS_SPEAKING.clear()


def pause_listening() -> None:
    global _LISTENING_ENABLED
    _LISTENING_ENABLED = False


def resume_listening() -> None:
    global _LISTENING_ENABLED
    _LISTENING_ENABLED = True


# -----------------------
# Whisper
# -----------------------
def _init_whisper():
    """Pick a model based on the active language. English -> distil-small.en
    (faster). Other languages -> small (multilingual)."""
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    if _WHISPER_BACKEND is None:
        return None
    lang = _current_whisper_lang()
    target = "distil-small.en" if lang == "en" else "small"
    if _WHISPER_MODEL is not None and _WHISPER_MODEL_NAME == target:
        return _WHISPER_MODEL
    try:
        if _WHISPER_BACKEND == "faster":
            _WHISPER_MODEL = WhisperModel(target, device="cpu", compute_type="int8")
        else:
            import whisper  # type: ignore
            # openai-whisper has no distil — collapse to 'small' for both branches
            _WHISPER_MODEL = whisper.load_model("small")
        _WHISPER_MODEL_NAME = target
    except Exception as e:
        # distil-small.en may not be present locally; fall back to small
        if target == "distil-small.en":
            try:
                if _WHISPER_BACKEND == "faster":
                    _WHISPER_MODEL = WhisperModel("small", device="cpu", compute_type="int8")
                    _WHISPER_MODEL_NAME = "small"
                    return _WHISPER_MODEL
            except Exception as e2:
                print(f"(whisper init failed: {e2})")
                _WHISPER_MODEL = None
                return None
        print(f"(whisper init failed: {e})")
        _WHISPER_MODEL = None
    return _WHISPER_MODEL


def _current_whisper_lang() -> str:
    try:
        import zendaya_languages as L
        return L.current().get("whisper", "en")
    except Exception:
        return "en"


def _audio_to_wav_bytes(audio_int16: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()


def _collapse_repetition(text: str) -> str:
    if not text:
        return text
    m = _REPETITION_RE.search(text)
    if not m:
        return text
    cut = text[: m.start() + len(m.group(1))]
    return cut.strip(" ,.;:") if cut.strip() else m.group(1).strip(" ,.;:")


def _whisper_decode(audio_int16: np.ndarray) -> tuple[str, float, float]:
    """Return (text, avg_logprob, no_speech_prob).

    avg_logprob = max across segments (best segment's confidence).
    no_speech_prob = max across segments (worst case — if any segment looks
    like silence, treat the whole thing as suspect).
    """
    model = _init_whisper()
    if model is None or audio_int16.size == 0:
        return ("", 0.0, 1.0)
    lang = _current_whisper_lang()
    try:
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        if _WHISPER_BACKEND == "faster":
            segments, _info = model.transcribe(
                audio_f32,
                beam_size=5,
                language=lang,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 250},
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            text_parts: list[str] = []
            best_logprob = -10.0
            worst_no_speech = 0.0
            for seg in segments:
                text_parts.append(seg.text.strip())
                if getattr(seg, "avg_logprob", None) is not None:
                    best_logprob = max(best_logprob, float(seg.avg_logprob))
                if getattr(seg, "no_speech_prob", None) is not None:
                    worst_no_speech = max(worst_no_speech, float(seg.no_speech_prob))
            return (" ".join(text_parts).strip(), best_logprob, worst_no_speech)
        else:
            result = model.transcribe(
                audio_f32,
                language=lang,
                fp16=False,
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            text = (result.get("text") or "").strip()
            # openai-whisper exposes avg_logprob/no_speech_prob per segment
            segs = result.get("segments") or []
            best_logprob = max((s.get("avg_logprob", -10.0) for s in segs), default=0.0)
            worst_no_speech = max((s.get("no_speech_prob", 0.0) for s in segs), default=0.0)
            return (text, float(best_logprob), float(worst_no_speech))
    except Exception as e:
        print(f"(whisper transcribe failed: {e})")
        return ("", 0.0, 1.0)


def _transcribe_google(audio_int16: np.ndarray) -> str:
    if not _SR_READY:
        return ""
    try:
        wav_bytes = _audio_to_wav_bytes(audio_int16)
        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio)
    except Exception:
        return ""


def _transcribe(audio_int16: np.ndarray) -> str:
    """Public — used by zendaya_hotkey. Denoise -> Whisper -> Google fallback."""
    global _DENOISER
    if _DENOISER is None:
        _DENOISER = Denoiser(enabled=True)
    if _DENOISER.ready:
        audio_int16 = _DENOISER.process_utterance(audio_int16)
    text, _logp, _nsp = _whisper_decode(audio_int16)
    if text:
        return _collapse_repetition(text)
    return _transcribe_google(audio_int16)


def _quality_ok(text: str, logp: float, no_speech: float) -> tuple[bool, str]:
    if not text:
        return (False, "empty")
    norm = text.strip().lower()
    if norm in HALLUCINATIONS:
        return (False, "hallucination-set")
    if no_speech > WHISPER_NO_SPEECH_MAX:
        return (False, f"no_speech={no_speech:.2f}")
    if logp < WHISPER_AVG_LOGPROB_MIN:
        return (False, f"avg_logprob={logp:.2f}")
    if len(norm) < 2:
        return (False, "too-short")
    return (True, "ok")


# -----------------------
# Audio capture
# -----------------------
def _audio_callback(indata, frames, time_info, status):
    try:
        flat = indata[:, 0] if indata.ndim > 1 else indata
        _AUDIO_Q.put_nowait(flat.copy())
    except queue.Full:
        try:
            _AUDIO_Q.get_nowait()
            _AUDIO_Q.put_nowait(flat.copy())
        except Exception:
            pass


def _frames():
    """Yield fixed 30 ms int16 frames (with AGC + denoise applied)."""
    buf = np.zeros(0, dtype=np.int16)
    while True:
        try:
            chunk = _AUDIO_Q.get(timeout=1.0)
        except queue.Empty:
            continue
        buf = np.concatenate([buf, chunk])
        while len(buf) >= FRAME_SAMPLES:
            raw = buf[:FRAME_SAMPLES].copy()
            buf = buf[FRAME_SAMPLES:]
            agc_out = _AGC.process(raw)
            den_out = _DENOISER.process(agc_out) if _DENOISER else agc_out
            yield den_out


def _drain_queue(keep_last_n: int = 0) -> None:
    try:
        while _AUDIO_Q.qsize() > keep_last_n:
            _AUDIO_Q.get_nowait()
    except Exception:
        pass


# -----------------------
# Utterance recording
# -----------------------
def _record_utterance(pre_roll: list[np.ndarray]) -> np.ndarray:
    """Record from the live frame stream until trailing silence or cap.

    Dynamic endpointing: short silence (0.45 s) ends the turn unless we
    haven't seen any speech yet; if still mid-utterance based on speech-frame
    count, require the longer silence (0.9 s) instead.
    """
    collected: list[np.ndarray] = list(pre_roll)
    speech_frames = 0
    silence_run_frames = 0
    total_frames = 0
    short_silence_frames = int(SHORT_SILENCE_END_S * 1000 / FRAME_MS)
    long_silence_frames = int(LONG_SILENCE_END_S * 1000 / FRAME_MS)
    max_frames = int(MAX_UTTERANCE_S * 1000 / FRAME_MS)
    saw_speech = False

    for frame in _frames():
        collected.append(frame)
        total_frames += 1
        if _VAD and _VAD.is_speech(frame):
            speech_frames += 1
            silence_run_frames = 0
            saw_speech = True
        else:
            silence_run_frames += 1
        if saw_speech:
            # Dynamic endpoint — longer hangover if utterance has been long
            need = long_silence_frames if speech_frames > 30 else short_silence_frames
            if silence_run_frames >= need:
                break
        else:
            # bail early if no speech materialises
            if total_frames > short_silence_frames * 3:
                break
        if total_frames >= max_frames:
            break

    if not collected:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(collected)


# -----------------------
# Main loop
# -----------------------
def _set_state(name: str, text: str = "") -> None:
    try:
        import zendaya as z
        if z._state_server:
            z._state_server.set_state(name, text)
    except Exception:
        pass


def _stop_tts() -> None:
    try:
        import zendaya as z
        if hasattr(z, "stop_speaking"):
            z.stop_speaking()
    except Exception:
        pass


def _run_listener_session() -> None:
    global _last_dispatch_ts, _DENOISER, _VAD, _WAKE

    if not _SD_READY:
        print(f"(voice listener v2 disabled — sounddevice missing: {_SD_ERR})")
        time.sleep(10)
        return

    if _WHISPER_BACKEND is None and not _SR_READY:
        print("(voice listener v2: no STT backend — install faster-whisper)")
        time.sleep(10)
        return

    # Lazy init heavy components on this thread
    _DENOISER = Denoiser(enabled=True)
    _VAD = SileroVAD(threshold=0.5)
    _WAKE = WakeEngine(model_name="hey_jarvis", threshold=0.5, barge_threshold=0.72)

    print("[voice v2] " + _DENOISER.diagnostics())
    print("[voice v2] " + _VAD.diagnostics())
    print("[voice v2] " + _WAKE.diagnostics())

    rolling_frames = int(ROLLING_BUFFER_S * 1000 / FRAME_MS)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        callback=_audio_callback,
    )

    try:
        stream.start()
        rolling: deque = deque(maxlen=rolling_frames)
        consecutive_speech = 0
        speech_triggered = False
        wake_fired = False
        barge_fired = False

        for frame in _frames():
            if not _LISTENING_ENABLED:
                rolling.clear()
                consecutive_speech = 0
                continue

            tts_on = _TTS_SPEAKING.is_set()

            # While TTS plays: only the wake engine listens, with stricter thresh.
            if tts_on:
                if _WAKE and _WAKE.ready:
                    if _WAKE.push(frame, barge_in=True):
                        barge_fired = True
                        print(f"[voice v2] BARGE-IN — score={_WAKE.last_score:.2f}")
                        _stop_tts()
                        # Wait briefly for TTS gate to clear, then proceed
                        deadline = time.time() + 1.5
                        while _TTS_SPEAKING.is_set() and time.time() < deadline:
                            time.sleep(0.03)
                        _drain_queue(keep_last_n=0)
                        rolling.clear()
                        consecutive_speech = 0
                        _set_state("listening")
                        # Drop into record path below
                        wake_fired = True
                        break
                # ignore everything else while TTS speaks
                continue

            rolling.append(frame)

            # Follow-up window — accept VAD-only activations to feel conversational
            in_followup = (time.time() - _last_dispatch_ts) < FOLLOW_UP_S

            if in_followup:
                # VAD activation
                if _VAD and _VAD.is_speech(frame):
                    consecutive_speech += 1
                    if consecutive_speech >= VAD_TRIGGER_FRAMES:
                        speech_triggered = True
                        break
                else:
                    consecutive_speech = 0
            else:
                # Cold path — wake-word gated
                if _WAKE and _WAKE.ready and _WAKE.push(frame, barge_in=False):
                    wake_fired = True
                    print(f"[voice v2] wake — score={_WAKE.last_score:.2f}")
                    break
                # If wake engine missing, fall back to VAD activation
                if (_WAKE is None or not _WAKE.ready) and _VAD and _VAD.is_speech(frame):
                    consecutive_speech += 1
                    if consecutive_speech >= VAD_TRIGGER_FRAMES:
                        speech_triggered = True
                        break
                else:
                    consecutive_speech = 0

        if not (speech_triggered or wake_fired or barge_fired):
            return  # outer loop restarts us

        _set_state("aware")
        _drain_queue(keep_last_n=50)

        # Verifier (cold wake only — followup and barge-in skip it)
        pre_roll_list = list(rolling)
        if wake_fired and not barge_fired:
            try:
                pre_roll_audio = np.concatenate(pre_roll_list) if pre_roll_list else np.zeros(0, dtype=np.int16)
                if pre_roll_audio.size >= int(SAMPLE_RATE * 0.4):
                    pre_text, _lp, _nsp = _whisper_decode(pre_roll_audio)
                    if pre_text and not verifier_passes(pre_text):
                        print(f"[voice v2] wake VERIFIER rejected: {pre_text!r}")
                        _set_state("idle")
                        return
            except Exception as e:
                print(f"[voice v2] verifier failed: {e}")

        _set_state("listening")

        audio = _record_utterance(pre_roll=pre_roll_list)

        if len(audio) < int(SAMPLE_RATE * MIN_UTTERANCE_S):
            _set_state("idle")
            return

        _set_state("thinking")

        # Heavy denoise on the full captured utterance (not per-frame)
        if _DENOISER is not None and _DENOISER.ready:
            audio = _DENOISER.process_utterance(audio)

        text, logp, no_speech = _whisper_decode(audio)
        cleaned = _collapse_repetition((text or "").strip())

        ok, reason = _quality_ok(cleaned, logp, no_speech)
        if not ok:
            print(f"[voice v2] dropped ({reason}): {cleaned!r}")
            _set_state("idle")
            return

        # Strip wake echo if Whisper transcribed it
        if wake_fired or barge_fired:
            cleaned = _WAKE_ECHO_RE.sub("", cleaned, count=1).strip(" ,.!?-")
            if not cleaned:
                # bare wake — acknowledge and update follow-up window
                _last_dispatch_ts = time.time()
                _set_state("aware")
                if _send_response:
                    try:
                        _send_response(random.choice(_BARE_WAKE_ACKS))
                    except Exception:
                        pass
                return

        print(f"[voice v2] you: {cleaned}")
        _last_dispatch_ts = time.time()
        if _handle_command:
            try:
                _handle_command(cleaned)
            except Exception as e:
                print(f"(command handler error: {e})")

    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass


def _listener_loop() -> None:
    while True:
        try:
            _run_listener_session()
        except Exception as e:
            print(f"(voice listener v2 crashed: {e}); restarting in 3s")
            time.sleep(3)


def start_voice_listener() -> threading.Thread:
    import zendaya as z
    global _handle_command, _send_response
    _handle_command = z.handle_user_command
    _send_response = z.send_response
    t = threading.Thread(target=_listener_loop, daemon=True, name="zendaya-voice-v2")
    t.start()
    return t


def diagnostics() -> str:
    lines = ["Voice listener v2 diagnostics:"]
    lines.append(f"  sounddevice:    {'OK' if _SD_READY else f'MISSING ({_SD_ERR})'}")
    lines.append(f"  whisper:        {_WHISPER_BACKEND or 'MISSING (pip install faster-whisper)'}")
    lines.append(f"  google STT:     {'OK' if _SR_READY else 'MISSING'}")
    # Probe each helper without starting the listener
    try:
        d = Denoiser(enabled=True); lines.append("  " + d.diagnostics())
    except Exception as e:
        lines.append(f"  denoise:        ERROR ({e})")
    try:
        v = SileroVAD(); lines.append("  " + v.diagnostics())
    except Exception as e:
        lines.append(f"  vad:            ERROR ({e})")
    try:
        w = WakeEngine(); lines.append("  " + w.diagnostics())
    except Exception as e:
        lines.append(f"  wake:           ERROR ({e})")
    if _SD_READY:
        try:
            dev = sd.query_devices(kind="input")
            lines.append(f"  default mic:    {dev['name']}")
        except Exception as e:
            lines.append(f"  default mic:    ERROR ({e})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(diagnostics())
