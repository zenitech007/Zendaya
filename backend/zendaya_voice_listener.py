"""
zendaya_voice_listener.py
=========================
Continuous Contextual Streaming Voice Listener (VAD-based).

Pipeline:
  microphone (16kHz int16) -> Rolling audio buffer
    -> Voice Activity Detection (webrtcvad / RMS)
    -> on detection: push 'aware' state to frontend
    -> record until trailing silence
    -> transcribe (Faster Whisper / Whisper / Google)
    -> Contextual Activation Engine (evaluates intent / keywords)
    -> dispatch to handle_user_command

Auto-mutes the mic while Zendaya is speaking (TTS).

Required:        sounddevice, numpy
Recommended:     faster-whisper or openai-whisper, webrtcvad
Fallback STT:    speech_recognition (Google Web Speech, online only)
"""

import io
import os
import queue
import random
import re
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
    _SD_READY = True
except Exception as e:
    _SD_READY = False
    _SD_ERR = str(e)

try:
    import webrtcvad
    _VAD_READY = True
except Exception:
    _VAD_READY = False

# Always-on neural wake-word detector. Runs on every frame; only AFTER it
# fires do we record + transcribe an utterance — same architecture Alexa /
# Hey Siri / Hey Google use.
_WAKE_ENGINE = None
_WAKE_READY = False
_WAKE_MODEL_NAME = os.environ.get("ZENDAYA_WAKE_MODEL", "hey_jarvis")
_WAKE_THRESHOLD = float(os.environ.get("ZENDAYA_WAKE_THRESHOLD", "0.5"))
try:
    import openwakeword
    from openwakeword.model import Model as _OWWModel
    _WAKE_READY = True
except Exception as _oww_err:
    _WAKE_READY = False
    _OWW_ERR = str(_oww_err)

try:
    import speech_recognition as sr
    _SR_READY = True
except Exception:
    _SR_READY = False

# Whisper backends — try faster-whisper first (lighter), then openai-whisper.
_WHISPER_BACKEND = None
_WHISPER_MODEL = None
try:
    from faster_whisper import WhisperModel  # type: ignore
    _WHISPER_BACKEND = "faster"
except Exception:
    try:
        import whisper  # type: ignore
        _WHISPER_BACKEND = "openai"
    except Exception:
        _WHISPER_BACKEND = None


# --- Config ---
SAMPLE_RATE = 16000          # Whisper wants 16kHz
CHANNELS = 1
VAD_FRAME_MS = 30            # webrtcvad requires 10/20/30 ms frames
MAX_UTTERANCE_S = 15.0       # hard cap on a single utterance
SILENCE_END_S = 1.0          # stop after this much trailing silence
ROLLING_BUFFER_S = 3.0       # Continuous rolling context buffer duration
FOLLOW_UP_S = 20.0           # after a successful turn, interaction probability increases
TTS_BLOCK_TIMEOUT = 30.0
VAD_TRIGGER_FRAMES = 5       # consecutive speech frames (~150ms) required to trip attention
MIN_UTTERANCE_S = 0.7        # below this, treat as noise and drop silently
NOISE_FLOOR_INIT = 300.0     # initial RMS noise floor (int16 units) before adaptation
NOISE_FLOOR_ALPHA = 0.02     # EMA smoothing on non-speech frames (smaller = slower drift)
SPEECH_FLOOR_MULT = 3.5      # utterance RMS must exceed noise_floor * this to transcribe
SPEECH_DYNAMIC_MIN = 800.0   # require some dynamic range too (peak/RMS ratio)

# Wake-word matcher: case-insensitive, tolerates leading filler + punctuation.
# The core pattern covers "Zendaya / Hey Zendaya / Hey Zen / Yo Zen / OK Zen"
# AND the most common Whisper mishears of those phrases (sin-day, send-aya,
# zen-day, sundae, sandia, the-end, send-her, zendia, send-i-uh, etc.).
# Mishears were inferred from the user's transcript log where "Hey Zendaya"
# came back as "before we end" / "let's go" / "send i uh".
_WAKE_FILLER = r"(?:hey|yo|ok|okay|hi|a|eh|uh|um)"
_WAKE_NAMES = (
    r"zendaya|zendia|zenday|zen\s*day|zen\s*deya|sandeya|sundae|sandia|"
    r"send\s*aya|send\s*i\s*uh|send\s*a|send\s*her|sin\s*day|sin\s*deya|"
    r"zander|sander|xander|zandra|santana|"
    r"the\s*end|then\s*the|zen\b|sen\b"
)
_WAKE_RE = re.compile(
    rf"^\s*(?:{_WAKE_FILLER}\s+)?(?:{_WAKE_NAMES})\b[\s,.\-!?]*(.*)$",
    re.IGNORECASE,
)
# Fuzzy fallback: short utterances (~ ≤ 5 words) get a difflib similarity
# check against the canonical wake phrases. Helps when Whisper outputs
# something not in the explicit alias list above.
_WAKE_CANONICAL = [
    "zendaya", "hey zendaya", "hey zen", "yo zen", "ok zendaya", "okay zendaya",
    "zen", "hey z",
]
_WAKE_FUZZY_THRESHOLD = 0.72
_BARE_WAKE_ACKS = ["Yes?", "I'm listening.", "Go ahead.", "What's up?"]


def _fuzzy_wake_match(text: str):
    """Return (rest, bare) if `text` is fuzzily close to a wake phrase, else None.

    Only applied to short utterances to avoid false positives on long speech.
    """
    import difflib
    norm = re.sub(r"[^a-z\s]", " ", text.lower()).strip()
    if not norm:
        return None
    words = norm.split()
    if len(words) > 5:
        return None
    # Try the whole utterance first (bare wake), then progressively shorter
    # prefixes — best-matching prefix wins, the remainder becomes the command.
    best = (0.0, None, "")
    for n in range(min(len(words), 4), 0, -1):
        candidate = " ".join(words[:n])
        for canon in _WAKE_CANONICAL:
            r = difflib.SequenceMatcher(None, candidate, canon).ratio()
            if r > best[0]:
                rest = " ".join(words[n:]).strip()
                best = (r, rest, candidate)
    if best[0] >= _WAKE_FUZZY_THRESHOLD:
        rest = best[1] or ""
        return (rest, not rest)
    return None

# --- State ---
_LISTENING_ENABLED = True
_TTS_SPEAKING = threading.Event()
_LISTENING_ENABLED = True

_HF_TOKEN = os.environ.get("HF_TOKEN") or "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"

try:
    import torch
    from pyannote.audio import Model
    from pyannote.audio.core.inference import Inference
    from scipy.spatial.distance import cdist
    _PYANNOTE_READY = True
    _PYANNOTE_MODEL = None
    _PYANNOTE_INFERENCE = None
except Exception as e:
    _PYANNOTE_READY = False
    _PYANNOTE_ERR = str(e)

_SPEAKER_PROFILES = []  # List of embedding arrays
_SPEAKER_AZIMUTHS = [0.0, 1.57, -1.57, 0.78, -0.78]  # Map speaker indices to physical directions (center, right, left, slight right, slight left)
_handle_command: Optional[Callable[[str], None]] = None
_send_response: Optional[Callable[[str], None]] = None
_AUDIO_Q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=400)
_last_dispatch_ts: float = 0.0
_noise_floor: float = NOISE_FLOOR_INIT


def _frame_rms(frame_int16: np.ndarray) -> float:
    if frame_int16.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(frame_int16.astype(np.float32) ** 2)))


def set_tts_speaking(speaking: bool):
    """Called by zendaya.send_response right before/after TTS playback."""
    if speaking:
        _TTS_SPEAKING.set()
    else:
        _TTS_SPEAKING.clear()


def pause_listening():
    global _LISTENING_ENABLED
    _LISTENING_ENABLED = False


def resume_listening():
    global _LISTENING_ENABLED
    _LISTENING_ENABLED = True




# --- Neural wake-word engine (always-on, gates dispatch like Alexa) ---
WAKE_CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms frames at 16kHz


def _init_wake_engine():
    """Build the openWakeWord model once. Returns None if unavailable."""
    global _WAKE_ENGINE
    if _WAKE_ENGINE is not None:
        return _WAKE_ENGINE
    if not _WAKE_READY:
        return None
    try:
        _WAKE_ENGINE = _OWWModel(
            wakeword_models=[_WAKE_MODEL_NAME],
            inference_framework="onnx",
        )
        return _WAKE_ENGINE
    except Exception as e:
        print(f"(wake engine init failed: {e})")
        return None


def _wake_predict(engine, audio_chunk_int16: np.ndarray) -> float:
    """Run wake-word inference on an 80ms chunk. Returns top confidence."""
    if engine is None:
        return 0.0
    try:
        scores = engine.predict(audio_chunk_int16)
    except Exception:
        return 0.0
    if not scores:
        return 0.0
    return float(max(scores.values()))


# --- VAD-based end-of-speech ---
def _make_vad():
    if not _VAD_READY:
        return None
    try:
        return webrtcvad.Vad(3)  # 0=least aggressive, 3=most — bumped to suppress fan/mic noise
    except Exception:
        return None


def _is_speech_vad(vad, frame_int16: np.ndarray) -> bool:
    if vad is None:
        rms = float(np.sqrt(np.mean(frame_int16.astype(np.float32) ** 2)))
        return rms > 350.0
    try:
        return vad.is_speech(frame_int16.tobytes(), SAMPLE_RATE)
    except Exception:
        return False


# --- Whisper / STT ---
def _init_whisper():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None or _WHISPER_BACKEND is None:
        return _WHISPER_MODEL
    try:
        # Multilingual 'small' covers English + Yoruba/Igbo/Hausa.
        # First load downloads ~470MB; cached afterwards.
        if _WHISPER_BACKEND == "faster":
            from faster_whisper import WhisperModel  # type: ignore
            _WHISPER_MODEL = WhisperModel("small", device="cpu", compute_type="int8")
        else:
            import whisper  # type: ignore
            _WHISPER_MODEL = whisper.load_model("small")
    except Exception as e:
        print(f"(whisper init failed: {e})")
        _WHISPER_MODEL = None
    return _WHISPER_MODEL


def _current_whisper_lang() -> str:
    """Look up the active Whisper language code from zendaya_languages, or 'en'."""
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


def _transcribe_whisper(audio_int16: np.ndarray) -> str:
    """Transcribe a recorded utterance. No initial_prompt — the wake engine
    gates dispatch, so we don't need to bias Whisper toward 'Zendaya'. The
    prompt was leaking into transcripts (e.g. 'The user will say things like
    Hey Zendaya...' appearing in your console)."""
    model = _init_whisper()
    if model is None:
        return ""
    lang = _current_whisper_lang()
    try:
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        if _WHISPER_BACKEND == "faster":
            segments, _info = model.transcribe(
                audio_f32,
                beam_size=5,
                language=lang,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        else:
            result = model.transcribe(
                audio_f32,
                language=lang,
                fp16=False,
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
            )
            return (result.get("text") or "").strip()
    except Exception as e:
        print(f"(whisper transcribe failed: {e})")
        return ""


_REPETITION_RE = re.compile(
    r"\b([\w\s'.,-]{3,40}?)([\s,.]+\1\b){2,}",
    re.IGNORECASE,
)


def _collapse_repetition(text: str) -> str:
    """Collapse Whisper repetition hallucinations like
    'open Chrome, open Chrome, open Chrome' into a single instance."""
    if not text:
        return text
    m = _REPETITION_RE.search(text)
    if not m:
        return text
    phrase = m.group(1).strip(" ,.;:")
    # Keep everything up to and including the first occurrence, drop the rest.
    cut = text[: m.start() + len(m.group(1))]
    return cut.strip(" ,.;:") if cut.strip() else phrase


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
    text = _transcribe_whisper(audio_int16)
    if text:
        return text
    return _transcribe_google(audio_int16)

# --- Speaker Recognition ---
def _get_speaker_azimuth(audio_int16: np.ndarray) -> float:
    global _PYANNOTE_MODEL, _PYANNOTE_INFERENCE, _SPEAKER_PROFILES
    if not _PYANNOTE_READY:
        return 0.0
    try:
        if _PYANNOTE_MODEL is None:
            print("[voice] Loading Pyannote speaker embedding model...")
            # We use torch.device("cuda" if torch.cuda.is_available() else "cpu")
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            _PYANNOTE_MODEL = Model.from_pretrained("pyannote/embedding", use_auth_token=_HF_TOKEN)
            _PYANNOTE_MODEL.to(device)
            _PYANNOTE_INFERENCE = Inference(_PYANNOTE_MODEL, window="whole")
            print("[voice] Pyannote loaded successfully.")

        # Convert numpy array to torch tensor with shape (channels, samples)
        # pyannote expects shape (1, num_samples) and floating point between -1 and 1
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_f32).unsqueeze(0)
        
        # Inference expects a dict with waveform and sample_rate
        embedding = _PYANNOTE_INFERENCE({"waveform": tensor, "sample_rate": SAMPLE_RATE})
        
        # Compare embedding to known profiles using cosine distance
        if not _SPEAKER_PROFILES:
            _SPEAKER_PROFILES.append(embedding)
            return _SPEAKER_AZIMUTHS[0]
            
        distances = cdist([embedding], _SPEAKER_PROFILES, metric="cosine")[0]
        min_dist_idx = np.argmin(distances)
        min_dist = distances[min_dist_idx]
        
        # Threshold for same speaker is usually around 0.3 - 0.4
        if min_dist < 0.4:
            return _SPEAKER_AZIMUTHS[min_dist_idx % len(_SPEAKER_AZIMUTHS)]
        else:
            # New speaker detected!
            _SPEAKER_PROFILES.append(embedding)
            new_idx = len(_SPEAKER_PROFILES) - 1
            azimuth = _SPEAKER_AZIMUTHS[new_idx % len(_SPEAKER_AZIMUTHS)]
            print(f"[voice] New speaker profile created! Assigned physical direction: {azimuth}")
            return azimuth

    except Exception as e:
        print(f"(speaker recognition failed: {e})")
        return 0.0


# --- Audio capture ---
def _audio_callback(indata, frames, time_info, status):
    if status:
        pass  # XRuns happen; ignore
    try:
        flat = indata[:, 0] if indata.ndim > 1 else indata
        _AUDIO_Q.put_nowait(flat.copy())
    except queue.Full:
        try:
            _AUDIO_Q.get_nowait()
            _AUDIO_Q.put_nowait(flat.copy())
        except Exception:
            pass


def _frames(samples_per_frame: int):
    """Generator yielding fixed-size int16 frames from the audio queue."""
    buf = np.zeros(0, dtype=np.int16)
    while True:
        try:
            chunk = _AUDIO_Q.get(timeout=1.0)
        except queue.Empty:
            continue
        buf = np.concatenate([buf, chunk])
        while len(buf) >= samples_per_frame:
            yield buf[:samples_per_frame].copy()
            buf = buf[samples_per_frame:]


# --- Recording an utterance ---
def _record_utterance(vad, vad_frame_samples: int, pre_roll_frames: int,
                      silence_end_frames: int, max_frames: int,
                      pre_roll: Optional[deque] = None) -> np.ndarray:
    """Record from the audio queue until we hit trailing silence or the cap."""
    collected: list = list(pre_roll) if pre_roll else []
    silence_run = 0
    speech_seen = False
    frames_seen = 0
    for vad_frame in _frames(vad_frame_samples):
        collected.append(vad_frame)
        frames_seen += 1
        speech = _is_speech_vad(vad, vad_frame)
        if speech:
            speech_seen = True
            silence_run = 0
        else:
            silence_run += 1
        if speech_seen and silence_run >= silence_end_frames:
            break
        if frames_seen >= max_frames:
            break
        # Bail early if no speech at all
        if not speech_seen and frames_seen >= silence_end_frames * 2:
            break
    if not collected:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(collected)


# --- Main loop ---
def _run_listener_session():
    global _last_dispatch_ts, _noise_floor

    if not _SD_READY:
        print(f"(voice listener disabled — sounddevice missing: {_SD_ERR})")
        print("  Install with: pip install sounddevice numpy")
        time.sleep(10)
        return

    vad = _make_vad()
    if vad is None:
        print("(webrtcvad not installed — using simple RMS gate; pip install webrtcvad-wheels)")

    if _WHISPER_BACKEND is None and not _SR_READY:
        print("(no STT backend available — install one of: faster-whisper, openai-whisper, SpeechRecognition)")
        time.sleep(10)
        return

    vad_frame_samples = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)
    rolling_frames = int(ROLLING_BUFFER_S * 1000 / VAD_FRAME_MS)
    silence_end_frames = int(SILENCE_END_S * 1000 / VAD_FRAME_MS)
    max_frames = int(MAX_UTTERANCE_S * 1000 / VAD_FRAME_MS)

    wake_engine = _init_wake_engine()
    if wake_engine is not None:
        print(f"(voice listener: wake-word gate active — model={_WAKE_MODEL_NAME!r}, threshold={_WAKE_THRESHOLD})")
    else:
        if _WAKE_READY:
            print("(voice listener: wake-word engine failed to init — falling back to VAD activation)")
        else:
            print("(voice listener: openwakeword not installed — falling back to VAD activation)")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=vad_frame_samples,
        callback=_audio_callback,
    )

    try:
        stream.start()
        rolling = deque(maxlen=rolling_frames)
        vad_iter = _frames(vad_frame_samples)
        wake_accum = np.zeros(0, dtype=np.int16)  # builds up to 80ms chunks

        try:
            import zendaya as z
        except Exception:
            z = None

        while True:
            speech_triggered = False
            consecutive_speech = 0
            wake_fired = False
            for frame_int16 in vad_iter:
                if not _LISTENING_ENABLED:
                    rolling.clear()
                    consecutive_speech = 0
                    wake_accum = np.zeros(0, dtype=np.int16)
                    continue

                # Barge-in TTS logic
                if _TTS_SPEAKING.is_set():
                    rolling.clear()
                    consecutive_speech = 0
                    wake_accum = np.zeros(0, dtype=np.int16)
                    continue

                rolling.append(frame_int16)

                # Always-on wake-word inference (Alexa-style).
                # Run only after the follow-up window has expired; inside it,
                # any VAD-confirmed speech counts as a command.
                in_followup = (time.time() - _last_dispatch_ts) < FOLLOW_UP_S
                if wake_engine is not None and not in_followup:
                    wake_accum = np.concatenate([wake_accum, frame_int16])
                    while len(wake_accum) >= WAKE_CHUNK_SAMPLES:
                        chunk = wake_accum[:WAKE_CHUNK_SAMPLES]
                        wake_accum = wake_accum[WAKE_CHUNK_SAMPLES:]
                        score = _wake_predict(wake_engine, chunk)
                        if score >= _WAKE_THRESHOLD:
                            wake_fired = True
                            print(f"[wake] fired ({_WAKE_MODEL_NAME}, score={score:.2f})")
                            break
                    if wake_fired:
                        break

                # Require N consecutive speech frames (~150ms) to avoid tripping on clicks/fan noise
                if _is_speech_vad(vad, frame_int16):
                    consecutive_speech += 1
                    if consecutive_speech >= VAD_TRIGGER_FRAMES:
                        speech_triggered = True
                        # Within follow-up: dispatch on VAD.
                        # Outside follow-up: ONLY dispatch on wake — VAD trips
                        # only adapt state, not record an utterance.
                        if in_followup or wake_engine is None:
                            break
                        else:
                            speech_triggered = False
                            consecutive_speech = 0
                else:
                    consecutive_speech = 0
                    # Adapt noise floor on confirmed-silence frames (EMA).
                    rms = _frame_rms(frame_int16)
                    _noise_floor = (1.0 - NOISE_FLOOR_ALPHA) * _noise_floor + NOISE_FLOOR_ALPHA * rms

            if not (speech_triggered or wake_fired):
                continue

            # Wake or VAD triggered attention — push 'aware' state
            if z and z._state_server:
                try:
                    z._state_server.set_state("aware")
                except Exception:
                    pass

            in_followup = (time.time() - _last_dispatch_ts) < FOLLOW_UP_S

            # Drop old backlog to maintain realtime execution
            try:
                while _AUDIO_Q.qsize() > 50:
                    _AUDIO_Q.get_nowait()
            except Exception:
                pass

            audio = _record_utterance(
                vad, vad_frame_samples, rolling_frames,
                silence_end_frames, max_frames, pre_roll=list(rolling),
            )
            rolling.clear()

            if len(audio) < SAMPLE_RATE * MIN_UTTERANCE_S:
                if z and z._state_server: z._state_server.set_state("idle")
                continue

            # Adaptive noise gate: drop utterances whose loudness or dynamic
            # range isn't meaningfully above the ambient noise floor — kills
            # the "B" / "Easy isn't it?" hallucinations from background noise.
            # Skipped on wake-fire since the wake engine already confirmed speech.
            utt_rms = _frame_rms(audio)
            utt_peak = float(np.max(np.abs(audio.astype(np.int32)))) if audio.size else 0.0
            if not wake_fired:
                if utt_rms < _noise_floor * SPEECH_FLOOR_MULT:
                    if z and z._state_server: z._state_server.set_state("idle")
                    continue
                if (utt_peak - utt_rms) < SPEECH_DYNAMIC_MIN:
                    if z and z._state_server: z._state_server.set_state("idle")
                    continue

            text = _transcribe(audio)
            cleaned = _collapse_repetition((text or "").strip())

            # Whisper hallucination filter (common silence/noise outputs)
            _hallucinations = {
                "thank you.", "thank you", "thanks.", "thanks", "thanks for watching.",
                "thanks for watching", "bye.", "bye", "you", "you.", ".", "?", "!",
                "subscribe.", "subscribe", "...", "uh.", "um.", "uh", "um",
                "okay.", "ok.", "yeah.", "yeah", "mm-hmm.", "mm-hmm",
                "thank you for watching.", "thank you for watching",
                "please subscribe.", "please subscribe",
            }
            if not cleaned or cleaned.lower() in _hallucinations:
                if z and z._state_server: z._state_server.set_state("idle")
                continue

            azimuth = _get_speaker_azimuth(audio)
            if z and z._state_server:
                try:
                    z._state_server.broadcast({
                        "type": "state_update",
                        "state": {"speakerAzimuth": azimuth}
                    })
                except Exception:
                    pass

            # --- Dispatch decision ---
            # Wake-engine path: any transcribed text counts as a command. If
            # the transcript is empty after stripping the wake word, treat
            # it as a bare wake call (acknowledge so it feels alive).
            # Fallback (no wake engine): old regex / fuzzy / contextual scoring.
            bare_wake = False
            do_dispatch = False

            if wake_fired:
                # Strip a leading wake-word echo if Whisper transcribed it too
                stripped = _WAKE_RE.sub("", cleaned, count=1).strip(" ,.!?-")
                if stripped:
                    cleaned = stripped
                else:
                    bare_wake = True
                do_dispatch = True
            elif in_followup:
                do_dispatch = True
            else:
                # No wake engine — fall back to text-based wake matching.
                lt_clean = cleaned.lower()
                wake_match = _WAKE_RE.match(cleaned)
                if wake_match:
                    rest = wake_match.group(1).strip(" ,.!?-")
                    if rest:
                        cleaned = rest
                    else:
                        bare_wake = True
                        cleaned = ""
                    do_dispatch = True
                else:
                    fuzzy = _fuzzy_wake_match(cleaned)
                    if fuzzy is not None:
                        rest, bare_wake = fuzzy
                        cleaned = rest if not bare_wake else ""
                        do_dispatch = True

            if do_dispatch:
                if bare_wake:
                    _last_dispatch_ts = time.time()
                    if _send_response:
                        try:
                            _send_response(random.choice(_BARE_WAKE_ACKS))
                        except Exception:
                            pass
                    if z and z._state_server:
                        try:
                            z._state_server.set_state("aware")
                        except Exception:
                            pass
                    continue
                print(f"[voice] you: {cleaned}")
                _last_dispatch_ts = time.time()
                if _handle_command:
                    try:
                        _handle_command(cleaned)
                    except Exception as e:
                        print(f"(command handler error: {e})")
            else:
                print(f"[voice - ignored context] you: {cleaned}")
                if z and z._state_server: z._state_server.set_state("idle")

    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

def _listener_loop():
    while True:
        try:
            _run_listener_session()
        except Exception as e:
            print(f"(voice listener crashed: {e}), restarting in 3 seconds...")
            time.sleep(3)



def start_voice_listener():
    import zendaya as z
    global _handle_command, _send_response
    _handle_command = z.handle_user_command
    _send_response = z.send_response

    t = threading.Thread(target=_listener_loop, daemon=True, name="zendaya-voice")
    t.start()
    return t


def diagnostics() -> str:
    """Print what's installed/missing — useful for debugging."""
    lines = ["Voice listener diagnostics:"]
    lines.append(f"  sounddevice:    {'OK' if _SD_READY else 'MISSING (pip install sounddevice)'}")
    lines.append(f"  webrtcvad:      {'OK' if _VAD_READY else 'MISSING — using RMS fallback (pip install webrtcvad-wheels)'}")
    lines.append(f"  whisper:        {_WHISPER_BACKEND or 'MISSING (pip install faster-whisper)'}")
    lines.append(f"  google STT:     {'OK' if _SR_READY else 'MISSING (pip install SpeechRecognition)'}")
    lines.append(f"  wake engine:    {'OK (' + _WAKE_MODEL_NAME + ')' if _WAKE_READY else 'MISSING (pip install openwakeword)'}")
    if _SD_READY:
        try:
            dev = sd.query_devices(kind="input")
            lines.append(f"  default mic:    {dev['name']}")
        except Exception as e:
            lines.append(f"  default mic:    ERROR ({e})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(diagnostics())
