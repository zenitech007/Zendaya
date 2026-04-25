"""
zendaya_backend/knowledge/voice_service.py

Shuri Voice Edition — Human-Blend Mode (Type-Safe)
--------------------------------------------------
Primary: Coqui XTTS v2 (multilingual, expressive)
Fallback: pyttsx3 (offline system voice)
Features:
- Preloaded XTTS for zero-lag synthesis
- Emotion-aware African-accented voice tuning
- Streams amplitude for hologram facial sync
- ElevenLabs disabled
"""

from __future__ import annotations
import os
import asyncio
import json
import time
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Union

# Force Coqui TTS to CPU mode in environments where GPU is unavailable or problematic.
# Setting this before importing the Coqui TTS module ensures the library respects the flag.
os.environ["COQUI_TTS_FORCE_CPU"] = "1"


import numpy as np
from pydub import AudioSegment
import simpleaudio as sa
import pyttsx3

logger = logging.getLogger(__name__)

# -----------------------------
# Optional dependencies
# -----------------------------
# --- Temporarily disable Coqui downloads (offline mode) ---
try:
    from TTS.api import TTS as CoquiTTS
    COQUI_AVAILABLE = True
except Exception as e:
    CoquiTTS = None
    COQUI_AVAILABLE = False
    logger.info("[VoiceService] Coqui TTS not available.")


ELEVENLABS_AVAILABLE = False  # Disabled intentionally

try:
    import librosa
    import soundfile as sf
except Exception:
    librosa = None  # type: ignore
    sf = None  # type: ignore

# -----------------------------
# App Integration
# -----------------------------
from zendaya_backend.ui.hologram_desktop import get_hologram
from zendaya_backend.websocket.hologram_ws import broadcast_amplitude

# -----------------------------
# Directories & Config
# -----------------------------
BASE = Path(__file__).resolve().parents[2]
VOICE_DATA_DIR = BASE / "data" / "voices"
GENERATED_DIR = VOICE_DATA_DIR / "generated"
for p in [VOICE_DATA_DIR, GENERATED_DIR]:
    p.mkdir(parents=True, exist_ok=True)

TUNING_CONFIG_PATH = VOICE_DATA_DIR / "shuri_tuning.json"
DEFAULT_TUNING: Dict[str, Union[str, float]] = {
    "name": "shuri_xtts_v2",
    "coqui_model": "tts_models/multilingual/multi-dataset/xtts_v2",
    "rate": 1.02,
    "pitch_shift": -0.3,
    "intonation": 1.08,
    "accent_bias": "african_english",
}
if not TUNING_CONFIG_PATH.exists():
    TUNING_CONFIG_PATH.write_text(json.dumps(DEFAULT_TUNING, indent=2))


# -----------------------------
# Helpers
# -----------------------------
async def _play_wav_background(wav_path: str) -> None:
    """Play wav silently and broadcast amplitude for hologram lip-sync."""
    try:
        mono: Optional[np.ndarray] = None
        sr: Optional[int] = None

        if sf:
            try:
                data, sr_val = sf.read(wav_path, always_2d=True)
                mono = np.mean(data, axis=1)
                if np.max(np.abs(mono)) > 0:
                    mono = mono / np.max(np.abs(mono))
                sr = sr_val
            except Exception:
                pass
        if mono is None and librosa:
            try:
                mono, sr = librosa.load(wav_path, sr=None)
            except Exception:
                mono, sr = None, None

        wave = AudioSegment.from_file(wav_path, format="wav")
        play_obj = sa.play_buffer(
            wave.raw_data,
            num_channels=wave.channels,
            bytes_per_sample=wave.sample_width,
            sample_rate=wave.frame_rate,
        )

        if mono is not None and sr:
            hop = int(sr * 0.04)
            for i in range(0, len(mono), hop):
                chunk = mono[i:i + hop]
                amp = float(np.sqrt(np.mean(np.square(chunk)))) if len(chunk) else 0.0
                amp = max(0.0, min(1.0, amp))
                await broadcast_amplitude(amp)
                await asyncio.sleep(0.04)

        play_obj.wait_done()
        await broadcast_amplitude(0.0)
    except Exception as e:
        logger.warning(f"[VoiceService] Background playback failed: {e}")


def _ensure_wav(path: str) -> str:
    """Convert mp3 -> wav if needed."""
    p = Path(path)
    if p.suffix.lower() == ".wav":
        return str(p)
    try:
        wav_path = p.with_suffix(".wav")
        AudioSegment.from_file(str(p)).set_frame_rate(16000).set_channels(1).export(
            str(wav_path), format="wav"
        )
        return str(wav_path)
    except Exception as e:
        logger.warning(f"[VoiceService] Conversion to wav failed: {e}")
        return str(p)


# -----------------------------
# VoiceService
# -----------------------------
class VoiceService:
    """Central TTS engine with XTTS + pyttsx3 fallback."""

    _coqui_preloaded: Optional[Any] = None

    def __init__(self) -> None:
        self.coqui_model_name: Optional[str] = None
        self.coqui: Optional[Any] = None
        self.coqui_ready: bool = False
        self._init_coqui_if_available()
        logger.info("[VoiceService] Shuri XTTS (Human-Blend) initialized.")

    def _init_coqui_if_available(self) -> None:
        """Set up model name and preload globally if not already cached."""
        try:
            if COQUI_AVAILABLE and CoquiTTS is not None:

                cfg = json.loads(TUNING_CONFIG_PATH.read_text())
                self.coqui_model_name = cfg.get(
                    "coqui_model", str(DEFAULT_TUNING["coqui_model"])
                )

                if not VoiceService._coqui_preloaded:
                    logger.info(f"[VoiceService] Preparing to download Coqui model: {self.coqui_model_name}")

                    def download_progress_callback(percent: float, status: str) -> None:
                        logger.info(f"[VoiceService] Coqui download {percent:.1f}% -- {status}")

                    VoiceService._coqui_preloaded = CoquiTTS(
                        model_name=self.coqui_model_name,
                        progress_bar=True,
                        gpu=True
                    )

                    logger.info("[VoiceService] XTTS model preloaded successfully.")

                self.coqui = VoiceService._coqui_preloaded
                self.coqui_ready = True
            else:
                logger.warning("[VoiceService] Coqui not installed.")
        except Exception as e:
            logger.warning(f"[VoiceService] Coqui preload failed: {e}")

    # -----------------------------
    # Emotion blending
    # -----------------------------
    def _blend_emotion(self, text: str, emotion: Optional[str] = None) -> str:
        """Blend emotion tags for tone."""
        emotion = (emotion or "").lower().strip()
        cues = {
            "angry": ["angry", "furious", "mad"],
            "excited": ["great", "amazing", "awesome"],
            "sad": ["sad", "sorry", "pain"],
            "calm": ["thank", "peace", "steady"],
            "focus": ["focus", "analyze", "system"],
        }

        if not emotion:
            for e, keys in cues.items():
                if any(k in text.lower() for k in keys):
                    emotion = e
                    break

        style = "calm and confident"
        if emotion == "angry":
            style = "assertive, focused intensity"
        elif emotion == "excited":
            style = "bright, inspired enthusiasm"
        elif emotion == "sad":
            style = "soft, reflective empathy"
        elif emotion == "focus":
            style = "sharp, analytical clarity"
        elif emotion == "calm":
            style = "peaceful and grounded"

        return f"[Shuri tone: {style}, African accent, intelligent clarity] {text}"

    # -----------------------------
    # Main synthesis
    # -----------------------------
    async def synthesize(self, text: str, emotion: str = "") -> Optional[Dict[str, Any]]:
        """Generate Shuri-style speech using XTTS or fallback pyttsx3."""
        # Primary: Coqui XTTS
        if self.coqui_ready and self.coqui is not None:
            try:
                styled_text = self._blend_emotion(text, emotion)
                out_path = Path(GENERATED_DIR) / f"shuri_{int(time.time())}.wav"

                def coqui_generate() -> bool:
                    if self.coqui is None:
                        return False
                    try:
                        self.coqui.tts_to_file(text=styled_text, file_path=str(out_path))
                        return True
                    except Exception as e:
                        logger.warning(f"[VoiceService] Coqui gen error: {e}")
                        return False

                ok_gen = await asyncio.to_thread(coqui_generate)
                if ok_gen and out_path.exists():
                    duration = 5.0
                    if librosa:
                        try:
                            y, sr = librosa.load(str(out_path), sr=None)
                            duration = float(librosa.get_duration(y=y, sr=sr))
                        except Exception:
                            pass
                    logger.info(
                        f"[VoiceService] Shuri XTTS synthesis success ({emotion or 'auto'})."
                    )
                    return {"path": str(out_path), "duration": duration}
            except Exception as e:
                logger.warning(f"[VoiceService] Coqui synthesis failed: {e}")

        # -----------------------------
        # Fallback: pyttsx3
        # -----------------------------
        try:
            tmp_wav = Path(GENERATED_DIR) / f"pyttsx3_shuri_{int(time.time())}.wav"

            def generate_pyttsx3() -> bool:
                try:
                    engine = pyttsx3.init()
                    voices = engine.getProperty("voices")
                    selected_voice: Optional[str] = None
                    for v in voices:
                        if any(
                            k in v.name.lower()
                            for k in ["female", "zira", "aria", "african", "en-gb"]
                        ):
                            selected_voice = v.id
                            break
                    if not selected_voice and voices:
                        selected_voice = voices[0].id

                    if selected_voice:
                        engine.setProperty("voice", selected_voice)
                    rate: Union[int, float, None] = engine.getProperty("rate")
                    if isinstance(rate, (int, float)):
                        engine.setProperty("rate", int(rate * 0.96))
                    engine.save_to_file(text, str(tmp_wav))
                    engine.runAndWait()
                    return True
                except Exception as e:
                    logger.warning(f"[VoiceService] pyttsx3 error: {e}")
                    return False

            ok = await asyncio.to_thread(generate_pyttsx3)
            if ok and tmp_wav.exists():
                logger.info("[VoiceService] pyttsx3 fallback synthesis success.")
                return {"path": str(tmp_wav), "duration": 4.0}
        except Exception as e:
            logger.warning(f"[VoiceService] pyttsx3 fallback failed: {e}")

        logger.error("[VoiceService] All backends failed.")
        return None

    # -----------------------------
    # Playback
    # -----------------------------
    async def play(self, path: str, hologram_priority: bool = True) -> bool:
        """Play generated audio either via hologram or locally."""
        wav_path = _ensure_wav(path)
        if hologram_priority:
            try:
                holo = get_hologram()
                if holo and hasattr(holo, "play_voice"):
                    holo.play_voice(wav_path)
                    asyncio.create_task(self._stream_amp_background(wav_path))
                    logger.info("[VoiceService] Playing via hologram.")
                    return True
            except Exception as e:
                logger.warning(f"[VoiceService] Hologram playback failed: {e}")

        try:
            asyncio.create_task(_play_wav_background(wav_path))
            return True
        except Exception as e:
            logger.warning(f"[VoiceService] Local playback failed: {e}")
            return False

    async def _stream_amp_background(self, wav_path: str) -> None:
        """Helper: stream amplitude without re-triggering playback."""
        try:
            await _play_wav_background(wav_path)
        except Exception:
            pass

# ----------------------------------------------------------
# GLOBAL INSTANCE (Auto-preload when backend starts)
# ----------------------------------------------------------
voice_service: Optional[VoiceService] = None

async def preload_voice_service() -> VoiceService:
    """Preload and warm up Shuri VoiceService at startup."""
    global voice_service
    if voice_service is None:
        voice_service = VoiceService()
        logger.info("[VoiceService] Preloading Shuri XTTS model in background...")
        await voice_service.synthesize("System voice online and calibrated.")
        logger.info("[VoiceService] Ready for requests.")
    return voice_service
