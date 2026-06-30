"""
voice output is handled by ElevenLabs TTS through the speak_async function, which sends text plus the current voice_id to ElevenLabs, retrieves MP3 audio, and plays it asynchronously so text streaming isn’t blocked. User responses are taken from typed console input (input()), and while no speech recognition is included, the script routes typed commands through parsers that detect mode switches, voice switches, system commands, searches, or normal chat. Switching voices happens when a user types something like “Zendaya, switch to narrator voice,” which the script catches with parse_voice_switch, resolves the requested preset or name with find_voice_by_free_text, updates MEM["current_voice_id"], and applies it to all future TTS. Switching modes between voice, text, or both is handled by parse_mode_switch and set_mode, which update memory and change whether replies are printed (stream_print), spoken (speak_async), or both. Finally, memory persistence via zendaya_memory.json stores the current mode, active voice, conversation history, and pending actions so the assistant remembers user preferences and context across sessions.
"""
# Suppress all deprecation warnings BEFORE any imports
import warnings
warnings.filterwarnings("ignore")

import sys as _sys_enc
for _stream in (_sys_enc.stdout, _sys_enc.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import re
import sys
import json
import time
import contextvars
import shutil
import random
import difflib # Added for fuzzy matching
import platform
import subprocess
import webbrowser
import threading # Added for async audio playback
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# --- Google API & Auth Imports ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Tier 1 Library Imports ---
import psutil
import pyperclip
import pyttsx3
import pygetwindow as gw
if platform.system() == "Windows":
    try:
        from win10toast import ToastNotifier
    except ImportError:
        pass  # Notifications silently disabled

# --- Python Library Imports ---
import requests
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from system.access import *
from integrations.home_assistant import ha_command as _ha_command, ha_available as _ha_available
from integrations.phone import kdec_command as _kdec_command
from integrations.spotify import spotify_command as _spotify_command
from perception.vision import (
    analyze_screen as _vision_analyze_screen,
    analyze_webcam as _vision_analyze_webcam,
    parse_vision_request as _parse_vision_request,
)
try:
    from memory.vector import (
        add_turn as _vmem_add,
        retrieve_relevant as _vmem_retrieve,
        format_for_prompt as _vmem_format,
    )
    _VMEM_READY = True
except Exception:
    _VMEM_READY = False
    def _vmem_add(role, text): pass
    def _vmem_retrieve(query, k=5, min_age_seconds=60.0): return []
    def _vmem_format(turns): return ""

if __name__ == "__main__":
    import sys as _sys_reg
    _sys_reg.modules.setdefault("zendaya", _sys_reg.modules["__main__"])

from skills.emotion import analyze_system_emotion

# Coder / agent / facts (graceful degrade — same pattern as the vector memory block above)
try:
    import skills.coder
    _CODER_READY = True
except Exception as _e:
    print(f"[zendaya] coder module unavailable: {_e}")
    skills.coder = None
    _CODER_READY = False

try:
    import skills.agent
    _AGENT_READY = True
except Exception as _e:
    print(f"[zendaya] agent module unavailable: {_e}")
    skills.agent = None
    _AGENT_READY = False

try:
    import skills.dev_voice
    from memory import project as _project
    _DEV_VOICE_READY = True
except Exception as _e:
    print(f"[zendaya] dev_voice module unavailable: {_e}")
    skills.dev_voice = None
    _project = None
    _DEV_VOICE_READY = False

try:
    import skills.jobs
    _JOBS_READY = True
except Exception as _e:
    print(f"[zendaya] jobs module unavailable: {_e}")
    skills.jobs = None
    _JOBS_READY = False

try:
    import skills.triggers
    _SKILLS_READY = True
except Exception as _e:
    print(f"[zendaya] skills module unavailable: {_e}")
    skills.triggers = None
    _SKILLS_READY = False

try:
    import skills.journal
    _JOURNAL_READY = True
except Exception as _e:
    print(f"[zendaya] journal module unavailable: {_e}")
    skills.journal = None
    _JOURNAL_READY = False

try:
    import perception.screen as _screen
    _SCREEN_READY = True
except Exception as _e:
    print(f"[zendaya] screen awareness module unavailable: {_e}")
    _screen = None
    _SCREEN_READY = False

try:
    import system.hotkey as _hotkey
    _HOTKEY_READY = True
except Exception as _e:
    print(f"[zendaya] hotkey module unavailable: {_e}")
    _hotkey = None
    _HOTKEY_READY = False

try:
    import memory.facts as _facts
    _FACTS_READY = True
except Exception as _e:
    print(f"[zendaya] facts module unavailable: {_e}")
    _facts = None
    _FACTS_READY = False

try:
    import system.installer
    _INSTALLER_READY = True
except Exception as _e:
    print(f"[zendaya] installer module unavailable: {_e}")
    system.installer = None
    _INSTALLER_READY = False

try:
    import skills.browser
    _BROWSER_READY = True
except Exception as _e:
    print(f"[zendaya] browser module unavailable: {_e}")
    skills.browser = None
    _BROWSER_READY = False

try:
    import integrations.github
    _GITHUB_READY = True
except Exception as _e:
    print(f"[zendaya] github module unavailable: {_e}")
    integrations.github = None
    _GITHUB_READY = False

try:
    import perception.uivision
    _UIVISION_READY = True
except Exception as _e:
    print(f"[zendaya] uivision module unavailable: {_e}")
    perception.uivision = None
    _UIVISION_READY = False

try:
    import skills.scheduler
    _SCHEDULER_READY = True
except Exception as _e:
    print(f"[zendaya] scheduler module unavailable: {_e}")
    skills.scheduler = None
    _SCHEDULER_READY = False

# For Windows specific window handling
if platform.system() == "Windows":
    try:
        import win32api, win32con, win32gui, win32process
    except ImportError:
        print("Warning: pywin32 not installed. Some advanced Windows window controls may not work.")

# Audio playback
try:
    import sounddevice as sd
    import soundfile as sf
    def playsound(file_path):
        data, samplerate = sf.read(file_path)
        sd.play(data, samplerate)
        sd.wait()
except ImportError:
    print("Warning: sounddevice not installed. Audio features disabled.")

# -----------------------
# Load keys & config  (MUST happen before any API client is created)
# -----------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize Gemini client AFTER loading the .env (guarded against re-import)
if "_gemini_client" not in dir():
    _gemini_client = None
    if GEMINI_API_KEY:
        try:
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            _GEMINI_READY = True
            print("✅ Gemini AI ready.")
        except Exception as e:
            print(f"Gemini API configuration failed: {e}")
            _GEMINI_READY = False
    else:
        _GEMINI_READY = False
        print("Warning: GEMINI_API_KEY is not set. Conversational features will be limited.")

_ELEVENLABS_READY = bool(ELEVENLABS_API_KEY)

# -----------------------
# Files, Constants & Scopes
# -----------------------
MEMORY_FILE = "zendaya_memory.json"
DEFAULT_MODE = "both"
PERSONA_NAME = "Zendaya"
ASSISTANT_NAME = "Zendaya"
ELEVENLABS_DEFAULT_VOICE_ID = "mxTlDrtKZzOqgjtBw4hM"

# --- Other Constants ---
AUTO_SEARCH_KEYWORDS = [
    "latest", "today", "breaking", "news", "trending", "score",
    "price", "weather", "exchange rate", "update", "who won", "market", "live",
    "forecast", "definition", "meaning", "how to", "what is"
]

# Force ElevenLabs voice ID - override memory settings
FORCE_ELEVENLABS_VOICE_ID = "mxTlDrtKZzOqgjtBw4hM"  # Zendaya's signature voice - NEVER CHANGE

# Google API Scopes
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --------------------------------------------------------
# 🔹 ElevenLabs TTS & System Fallback
# --------------------------------------------------------
_TTS_ENGINE = None

def _set_tts_gate(speaking: bool):
    """Tell the voice listener(s) to ignore the mic while we're speaking."""
    for mod_name in ("zendaya_voice_live", "voice.listener", "voice.listener_v2"):
        try:
            mod = sys.modules.get(mod_name)
            if mod is not None and hasattr(mod, "set_tts_speaking"):
                mod.set_tts_speaking(speaking)
        except Exception:
            pass


_TTS_PCM_RATE = 22050  # ElevenLabs pcm_22050 — fastest streaming, no MP3 decode
_TTS_STOP = threading.Event()
_TTS_UTT_ID = 0  # monotonic per-utterance id; the HUD drops chunks from stale ids

def _next_utt_id() -> int:
    global _TTS_UTT_ID
    _TTS_UTT_ID += 1
    return _TTS_UTT_ID

def stop_speaking():
    """Cut off any in-progress TTS playback. Used for barge-in from voice listener."""
    _TTS_STOP.set()
    # Tell any HUD client to flush its audio queue immediately.
    if _state_server is not None:
        try:
            _state_server.audio_stop()
        except Exception:
            pass

def _stream_pcm_playback(response, samplerate: int = _TTS_PCM_RATE):
    """Play raw PCM int16 chunks from a streaming HTTP response with low latency.

    Sink is chosen ONCE per utterance: if a HUD client is connected the PCM is
    teed to the browser over the WebSocket (and the local speaker is skipped);
    otherwise it plays on the local sounddevice stream. Amplitude + visemes are
    pushed on BOTH paths so the orb lip-sync is identical either way.
    """
    import numpy as _np

    utt_id = _next_utt_id()
    to_hud = False
    if _state_server is not None:
        try:
            to_hud = _state_server.hud_client_count() > 0
        except Exception:
            to_hud = False

    stream = None
    if to_hud:
        try:
            _state_server.audio_begin(samplerate, utt_id)
        except Exception:
            to_hud = False  # if we can't announce, fall back to local speaker

    if not to_hud:
        stream = sd.OutputStream(samplerate=samplerate, channels=1, dtype="int16")
        stream.start()

    try:
        leftover = b""
        seq = 0
        for chunk in response.iter_content(chunk_size=4096):
            if _TTS_STOP.is_set():
                break
            if not chunk:
                continue
            data = leftover + chunk
            if len(data) % 2:
                leftover = data[-1:]
                data = data[:-1]
            else:
                leftover = b""
            if data:
                samples = _np.frombuffer(data, dtype=_np.int16)
                if to_hud:
                    try:
                        _state_server.push_audio_chunk(data, utt_id, seq)
                        seq += 1
                    except Exception:
                        pass
                elif stream is not None:
                    stream.write(samples)
                if _state_server is not None and len(samples):
                    try:
                        samples_f32 = samples.astype(_np.float32) / 32768.0
                        rms = float(_np.sqrt(_np.mean(samples_f32 ** 2)))
                        # Speech RMS rarely exceeds ~0.25; scale into a usable 0–1 range.
                        level = min(1.0, rms * 4.0)
                        _state_server.set_amplitude(level)
                        try:
                            import voice.visemes as _viz
                            # Real formant-based weights derived from the PCM window.
                            # Falls back to the char-schedule player if analysis errors.
                            try:
                                _viz.ANALYZER.samplerate = samplerate
                                weights = _viz.ANALYZER.analyze(samples_f32, rms)
                            except Exception:
                                weights = _viz.PLAYER.current()
                                weights = {k: v * level for k, v in weights.items()}
                            _state_server.set_visemes(weights)
                        except Exception:
                            pass
                    except Exception:
                        pass
    finally:
        if to_hud and _state_server is not None:
            try:
                _state_server.audio_end(utt_id)
            except Exception:
                pass
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if _state_server is not None:
            try:
                _state_server.set_amplitude(0.0)
                _state_server.set_visemes({"aa": 0, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
            except Exception:
                pass
        try:
            import voice.visemes as _viz
            _viz.PLAYER.stop()
            try:
                _viz.ANALYZER.reset()
            except Exception:
                pass
        except Exception:
            pass

def _speak_offline_async(text: str):
    """Synthesize with the offline Coqui engine and play through the shared
    PCM/viseme pipeline (same path as ElevenLabs). Falls back to system TTS."""
    import voice.offline_tts as _offline_tts

    def _run():
        _TTS_STOP.clear()
        _set_tts_gate(True)
        try:
            import voice.visemes as _viz
            _viz.PLAYER.start(_viz.build_schedule(text))
            try:
                _viz.ANALYZER.reset()
            except Exception:
                pass
        except Exception:
            pass
        try:
            pcm = _offline_tts.synth_to_pcm(text, target_sr=_TTS_PCM_RATE)
            if not pcm:
                speak_system_fallback(text)
            elif not _TTS_STOP.is_set():
                _stream_pcm_playback(
                    _offline_tts.PcmBytesResponse(pcm), samplerate=_TTS_PCM_RATE
                )
        except Exception as e:
            print(f"(Offline TTS failed: {e})")
            speak_system_fallback(text)
        finally:
            _set_tts_gate(False)

    threading.Thread(target=_run, daemon=True).start()

def speak_async(text: str, voice_id: str):
    """Streams ElevenLabs TTS and plays as bytes arrive (low-latency)."""
    # Offline-first hybrid: unless the user selected ElevenLabs, speak offline.
    try:
        import voice.offline_tts as _offline_tts
        _engine_pref = _offline_tts.get_voice_engine()
    except Exception:
        _offline_tts = None
        _engine_pref = "elevenlabs"
    if _offline_tts is not None and _engine_pref == "offline":
        _speak_offline_async(text)
        return

    # Per-language voice override: if the active language has its own voice ID,
    # use it; otherwise fall back to Zendaya's default voice.
    _lang_voice = None
    try:
        if _lang is not None:
            _lang_voice = _lang.voice_id_for()
    except Exception:
        _lang_voice = None
    voice_id = _lang_voice or FORCE_ELEVENLABS_VOICE_ID

    enhanced_settings = {
        "stability": 0.75,
        "similarity_boost": 0.85,
        "style": 0.25,
        "use_speaker_boost": True
    }

    if not _ELEVENLABS_READY or 'sd' not in globals() or not is_connected():
        # Offline-first: prefer the offline engine over robotic system TTS.
        if _offline_tts is not None:
            _speak_offline_async(text)
        else:
            speak_system_fallback(text)
        return

    # Pick TTS model: turbo_v2_5 is fast English-only; multilingual_v2 covers
    # Yoruba/Igbo/Hausa/Pidgin (Pidgin reads phonetically through English).
    _tts_model_id = "eleven_turbo_v2_5"
    try:
        if _lang is not None and _lang.current_name() != "english":
            _tts_model_id = "eleven_multilingual_v2"
    except Exception:
        pass

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "audio/pcm",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    payload = {
        "text": text,
        "model_id": _tts_model_id,
        "voice_settings": enhanced_settings,
        "output_format": "pcm_22050",
        "optimize_streaming_latency": 3,
    }
    params = {"output_format": "pcm_22050", "optimize_streaming_latency": 3}

    def _run():
        _TTS_STOP.clear()
        _set_tts_gate(True)
        try:
            import voice.visemes as _viz
            _viz.PLAYER.start(_viz.build_schedule(text))
            try:
                _viz.ANALYZER.reset()
            except Exception:
                pass
        except Exception:
            pass
        try:
            with requests.post(url, json=payload, headers=headers, params=params,
                               stream=True, timeout=20) as r:
                if r.status_code != 200:
                    print(f"(ElevenLabs API Error: {r.status_code} - {r.text[:200]})")
                    speak_system_fallback(text)
                    return
                _stream_pcm_playback(r)
        except Exception as e:
            print(f"(ElevenLabs stream failed: {e})")
            speak_system_fallback(text)
        finally:
            _set_tts_gate(False)

    threading.Thread(target=_run, daemon=True).start()

def initialize_system_tts():
    """Initializes the pyttsx3 engine as a fallback."""
    global _TTS_ENGINE
    if _TTS_ENGINE: return True
    try:
        print("🔄 Initializing system Text-to-Speech engine as fallback...")
        _TTS_ENGINE = pyttsx3.init()
        voices = _TTS_ENGINE.getProperty('voices')
        female_voice = next((voice for voice in voices if voice.gender == 'female'), None)
        if female_voice:
            _TTS_ENGINE.setProperty('voice', female_voice.id)
        print("✅ System TTS engine loaded.")
        return True
    except Exception as e:
        print(f"❌ CRITICAL: Failed to initialize system TTS engine. Voice output will be disabled.")
        print(f"   Error details: {e}")
        return False

def speak_system_fallback(text: str):
    """Speak text using the system TTS engine silently (no duplicate print)."""
    if not initialize_system_tts():
        print("⚠️ TTS engine not ready.")
        return
    _set_tts_gate(True)
    try:
        _TTS_ENGINE.say(text)
        _TTS_ENGINE.runAndWait()
    except Exception as e:
        print(f"Error during system TTS playback: {e}")
    finally:
        _set_tts_gate(False)


# -----------------------
# Weather (Open-Meteo — no API key needed)
# -----------------------
def get_weather_greeting() -> Optional[str]:
    try:
        geo = requests.get("https://ipinfo.io/json", timeout=5).json()
        lat, lon = geo.get("loc", "0,0").split(",")
        city = geo.get("city", "your area")
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weather_code"
            f"&temperature_unit=celsius&timezone=auto"
        )
        data = requests.get(url, timeout=5).json()
        current = data.get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code", -1)
        wmo = {
            0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
            61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
            75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "heavy showers",
            95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms",
        }
        desc = wmo.get(code, "mixed conditions")
        if temp is not None:
            return f"It's currently {temp:.0f} degrees in {city} with {desc}."
        return None
    except Exception:
        return None

# -----------------------
# Memory persistence
# -----------------------
def load_memory() -> Dict[str, Any]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {
        "mode": DEFAULT_MODE, "convo": [],
        "inside_jokes": [], "pending_confirm": None, "pending_choice": None, "pending_proactive": None, "user_name": None,
        "command_history": [], "routines": {}, "summaries": [],
        "professional_mode": False,
        "current_voice_id": ELEVENLABS_DEFAULT_VOICE_ID,
        "last_action": None, "pending_action": None,
        "last_system_command": None,
        "language": "english",
        "proactive_enabled": True,
        "vision_enabled": False,
        "gestures_enabled": False,
        "screen_awareness_enabled": False,
        "face_mode": "pet",
        "hud_enabled": True,
    }

def save_memory(mem: Dict[str, Any]) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(Memory save error: {e})")

MEM = load_memory()

# Sync language module with persisted preference
try:
    import skills.languages as _lang
    _lang.set_current(MEM.get("language", "english"))
except Exception:
    _lang = None

# -----------------------
# Context tracking helpers
# -----------------------
def set_last_action(entity_type: str, name: str, path: str):
    MEM["last_action"] = {"type": entity_type, "name": name, "path": path}
    save_memory(MEM)

def set_last_system_command(sys_result: str):
    result_lower = sys_result.lower()
    if any(kw in result_lower for kw in ["volume", "audio", "mute", "unmute"]):
        MEM["last_system_command"] = "volume"
    elif "brightness" in result_lower:
        MEM["last_system_command"] = "brightness"
    else:
        return
    save_memory(MEM)

def resolve_context(text: str) -> str:
    last = MEM.get("last_action")
    if not last:
        return text
    folder_refs = ["the folder", "that folder", "the directory", "in there", "same folder", "that directory"]
    file_refs = ["the file", "that file", "the document", "that document"]
    for ref in folder_refs:
        if ref in text.lower():
            if last["type"] == "folder":
                repl = f'"{last["path"]}"'
                text = re.sub(re.escape(ref), lambda _m: repl, text, count=1, flags=re.IGNORECASE)
            elif last["type"] == "file":
                parent = os.path.dirname(last["path"])
                repl = f'"{parent}"'
                text = re.sub(re.escape(ref), lambda _m: repl, text, count=1, flags=re.IGNORECASE)
            break
    for ref in file_refs:
        if ref in text.lower():
            if last["type"] == "file":
                repl = f'"{last["path"]}"'
                text = re.sub(re.escape(ref), lambda _m: repl, text, count=1, flags=re.IGNORECASE)
            break
    return text

# -----------------------
# Core Assistant Functions
# -----------------------
def stream_print(text: str, delay: float = 0.01):
    print(f"{ASSISTANT_NAME}: ", end="")
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

try:
    import server.state_server as _state_server
except Exception:
    _state_server = None  # FastAPI/uvicorn missing — run headless without Godot bridge

_BODY_KEYWORDS = (
    ("nod",   ("yes ", "yes,", "yes.", "yep", "got it", "agreed", "confirmed",
               "absolutely", "of course", "sure thing", "on it")),
    ("shake", ("no ", "no,", "no.", "nope", "can't ", "won't ", "unable",
               "sorry", "i don't think")),
    ("wave",  ("hello", "hi ", "hey ", "welcome back", "good morning",
               "good night", "farewell", "goodbye", "see you")),
    ("shrug", ("not sure", "maybe", "i don't know", "could go either")),
)


def _classify_body(text: str) -> Optional[str]:
    low = (text or "").lower()
    for action, kws in _BODY_KEYWORDS:
        if any(kw in low for kw in kws):
            return action
    return None


import contextlib

_REPLY_CAPTURE: "contextvars.ContextVar[list[str] | None]" = contextvars.ContextVar(
    "zendaya_reply_capture", default=None
)


@contextlib.contextmanager
def capture_replies():
    """While active, every send_response(text) also appends text to the
    yielded list. Used by the mobile sync chat path to return the reply.

    Caveat: contextvars do not propagate to threads spawned via
    threading.Thread, so this only captures replies emitted on the calling
    thread (the current handle_user_command path is synchronous)."""
    buf: list[str] = []
    token = _REPLY_CAPTURE.set(buf)
    try:
        yield buf
    finally:
        _REPLY_CAPTURE.reset(token)


def _bridge_user_message_sync(msg: str) -> str:
    """Run the command handler and return the assistant's reply text
    (newline-joined). Empty string if the handler produced no reply."""
    with capture_replies() as buf:
        try:
            handle_user_command(msg)
        except Exception as e:
            return f"[error: {e}]"
    return "\n".join(buf)


def send_response(text: str):
    _buf = _REPLY_CAPTURE.get()
    if _buf is not None:
        _buf.append(text)
    if MEM["mode"] in ("both", "text"):
        stream_print(text)
    if MEM["mode"] in ("both", "voice"):
        speak_async(text, FORCE_ELEVENLABS_VOICE_ID)
    if _state_server is not None:
        try:
            _state_server.set_state("talking", text)
        except Exception:
            pass
        try:
            action = _classify_body(text)
            if action:
                _state_server.set_body_action(action)
        except Exception:
            pass

# -------------------------------------------------
# TIER 1 FEATURE: GOOGLE API SECURE AUTHENTICATION
# -------------------------------------------------
def get_google_service(api_name: str, api_version: str, scopes: List[str]):
    """Handles the OAuth2 flow and returns an authenticated service object."""
    creds = None
    token_file = f'token_{api_name}.json'
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Could not refresh token for {api_name}: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists('credentials.json'):
                try:
                    log_event("google_auth", "credentials.json missing", {"api": api_name})
                except Exception:
                    pass
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes)
            creds = flow.run_local_server(port=0)
        
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
            
    try:
        service = build(api_name, api_version, credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred building the service: {error}')
        return None

# -------------------------------------------------
# TIER 1 FEATURE: EMAIL & CALENDAR (Functional)
# -------------------------------------------------
def check_email(max_results: int = 3) -> str:
    service = get_google_service('gmail', 'v1', GMAIL_SCOPES)
    if not service:
        if not os.path.exists('credentials.json'):
            return ("Gmail isn't set up yet — drop a Google OAuth `credentials.json` "
                    "into the backend folder and I'll handle the rest.")
        return "I couldn't connect to your Gmail account."
    try:
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
        messages = results.get('messages', [])
        if not messages:
            return "Your inbox is clear. No unread emails."
        email_summaries = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'] == 'Subject')
            sender = next(h['value'] for h in headers if h['name'] == 'From')
            email_summaries.append(f"From {sender.split('<')[0].strip()}, subject: {subject}")
        return f"You have {len(messages)} unread emails. Here are the latest:\n" + "\n".join(email_summaries)
    except HttpError as error:
        return f"An error occurred checking email: {error}"

def check_calendar(max_results: int = 5) -> str:
    service = get_google_service('calendar', 'v3', CALENDAR_SCOPES)
    if not service:
        if not os.path.exists('credentials.json'):
            return ("Google Calendar isn't set up yet — drop a Google OAuth "
                    "`credentials.json` into the backend folder and I'll handle the rest.")
        return "I couldn't connect to your Google Calendar."
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return "You have no upcoming events."
        event_summaries = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = datetime.fromisoformat(start)
            formatted_time = start_dt.strftime('%A at %I:%M %p')
            event_summaries.append(f"- {event['summary']} on {formatted_time}")
        return f"Here are your next {len(events)} events:\n" + "\n".join(event_summaries)
    except HttpError as error:
        return f"An error occurred checking the calendar: {error}"

# -------------------------------------------------
# TIER 1 FEATURE: SYSTEM MONITORING, CLIPBOARD, FILES
# -------------------------------------------------
def get_system_performance() -> str:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return f"System status: CPU at {cpu}%. Memory at {mem.percent}%. Disk at {disk.percent}%."

def read_clipboard() -> str:
    try:
        content = pyperclip.paste()
        return f"Clipboard contains: {content}" if content else "The clipboard is empty."
    except Exception:
        return "Sorry, I couldn't read the clipboard."

def write_to_clipboard(text: str) -> str:
    try:
        pyperclip.copy(text)
        return "Copied to clipboard."
    except Exception:
        return "I couldn't write to the clipboard."

def find_file(filename: str, search_path: str = None) -> str:
    path = search_path or os.path.expanduser("~")
    send_response(f"Searching for '{filename}'...")
    for root, _, files in os.walk(path):
        if filename in files:
            found = os.path.join(root, filename)
            return f"File found at: {found}"
    return f"Couldn't find '{filename}'."

def read_file_content(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content) > 2000:
            send_response("File is large, summarizing...")
            response = _gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Summarize this:\n\n{content[:2000]}"
            )
            ai_text = response.text
            return f"Summary:\n{ai_text.strip()}"
        return f"Content:\n{content}"
    except Exception as e:
        return f"Error reading file: {e}"

def generate_and_write_file(description: str, filename: str, filepath: str) -> str:
    """Use Gemini to generate file content, then write it to disk."""
    if not _GEMINI_READY:
        return "I can't generate content right now — my AI engine is offline."

    ext = os.path.splitext(filename)[1].lower()
    type_hints = {
        ".html": "HTML", ".css": "CSS", ".js": "JavaScript", ".jsx": "React JSX",
        ".ts": "TypeScript", ".tsx": "React TSX", ".py": "Python", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".sh": "Bash shell script", ".bat": "Windows batch",
        ".sql": "SQL", ".json": "JSON", ".xml": "XML", ".md": "Markdown",
        ".txt": "plain text",
    }
    file_type = type_hints.get(ext, f"{ext} file" if ext else "plain text")

    generation_prompt = (
        f"Generate ONLY the raw file content for a {file_type} file. "
        f"User's request: {description}\n"
        f"Output ONLY the file content — no explanation, no markdown code fences, "
        f"no backticks, no commentary. Just the raw content that should be saved to disk."
    )

    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=generation_prompt
        )
        content = response.text.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
            else:
                content = "\n".join(lines[1:])

        result = write_file(filepath, content)
        if "written" in result.lower():
            return f"Done! I wrote the {file_type} file to: {filepath}"
        return result
    except Exception as e:
        return f"I generated the content but couldn't write it: {e}"


def analyze_file_content(filepath: str, user_request: str) -> str:
    """Read a file and use Gemini to analyze it based on the user's request."""
    try:
        expanded = os.path.expandvars(os.path.expanduser(filepath))
        if not os.path.isfile(expanded):
            return f"I can't find the file: {expanded}"

        with open(expanded, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        if not content.strip():
            return f"The file '{os.path.basename(expanded)}' is empty."

        if not _GEMINI_READY:
            if len(content) > 2000:
                return f"File content (truncated):\n{content[:2000]}..."
            return f"File content:\n{content}"

        max_chars = 30000
        truncated = content[:max_chars]
        if len(content) > max_chars:
            truncated += f"\n\n[...truncated, {len(content)} total characters]"

        ext = os.path.splitext(expanded)[1]
        analysis_prompt = (
            f"The user asked: \"{user_request}\"\n\n"
            f"Here is the content of the file '{os.path.basename(expanded)}' ({ext}):\n\n"
            f"{truncated}\n\n"
            f"Analyze this file and respond to the user's request. "
            f"Be specific about what the code/content does. "
            f"Keep your response concise but thorough."
        )

        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=analysis_prompt
        )
        return response.text.strip()

    except UnicodeDecodeError:
        return "This file appears to be binary — I can only read text-based files."
    except Exception as e:
        return f"Error reading file: {e}"


def edit_file_with_ai(filepath: str, modification: str) -> str:
    """Read a file, apply AI-generated modifications, and write it back."""
    if not _GEMINI_READY:
        return "I can't edit files right now — my AI engine is offline."

    expanded = os.path.expandvars(os.path.expanduser(filepath))
    if not os.path.isfile(expanded):
        return f"I can't find the file: {expanded}"

    try:
        with open(expanded, 'r', encoding='utf-8', errors='replace') as f:
            original_content = f.read()
    except Exception as e:
        return f"Error reading {os.path.basename(expanded)}: {e}"

    if not original_content.strip():
        return f"The file '{os.path.basename(expanded)}' is empty — there's nothing to modify."

    ext = os.path.splitext(expanded)[1]
    edit_prompt = (
        f"Here is the current content of '{os.path.basename(expanded)}' ({ext}):\n\n"
        f"{original_content}\n\n"
        f"The user wants this modification: {modification}\n\n"
        f"Apply the requested change and output ONLY the complete modified file content. "
        f"No explanations, no markdown fences, no backticks — just the raw modified file content."
    )

    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=edit_prompt
        )
        new_content = response.text.strip()

        if new_content.startswith("```"):
            lines = new_content.split("\n")
            if lines[-1].strip() == "```":
                new_content = "\n".join(lines[1:-1])
            else:
                new_content = "\n".join(lines[1:])

        backup_path = expanded + ".bak"
        try:
            shutil.copy2(expanded, backup_path)
        except Exception:
            pass

        result = write_file(expanded, new_content)
        if "written" in result.lower():
            return (
                f"Done! I've modified '{os.path.basename(expanded)}'. "
                f"A backup was saved as '{os.path.basename(backup_path)}'."
            )
        return result
    except Exception as e:
        return f"Failed to apply changes: {e}"


def manage_file(action: str, source: str, destination: str = None) -> str:
    if not os.path.exists(source): return f"Source '{source}' does not exist."
    try:
        if action == "copy":
            if not destination: return "I need a destination."
            shutil.copy(source, destination)
            return f"Copied '{os.path.basename(source)}'."
        elif action == "move":
            if not destination: return "I need a destination."
            shutil.move(source, destination)
            return f"Moved '{os.path.basename(source)}'."
        elif action == "delete":
            MEM["pending_confirm"] = {"action": "delete_file", "path": source}
            save_memory(MEM)
            return f"Please confirm deletion of '{os.path.basename(source)}'."
    except Exception as e:
        return f"Error: {e}"

def show_notification(title: str, message: str) -> str:
    if platform.system() == "Windows" and 'ToastNotifier' in globals():
        ToastNotifier().show_toast(title, message, duration=10, threaded=True)
        return "Notification sent."
    return "Notifications only supported on Windows with win10toast installed."

# -----------------------
# Tavily search
# -----------------------
def tavily_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return "(Search unavailable — missing TAVILY_API_KEY)"
    if not is_connected():
        return "(Search unavailable — no internet connection)"
    try:
        r = requests.post("https://api.tavily.com/search",
                          json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 5},
                          timeout=25)
        data = r.json()
        items = data.get("results", [])
        if not items:
            return "No search results found."
        lines = []
        for it in items:
            title = it.get("title", "untitled")
            snippet = (it.get("content") or "")[:220].replace("\n", " ")
            lines.append(f"- {title}: {snippet} (source)")
        return "\n".join(lines)
    except Exception as e:
        return f"(Search error: {e})"

def should_auto_search(txt: str) -> bool:
    l = txt.lower()
    return any(k in l for k in AUTO_SEARCH_KEYWORDS)

# -----------------------
# Gemini reply composition
# -----------------------
SYSTEM_PROMPT = (
    "You are Zendaya, a brilliant, witty, confident, and slightly teasing AI assistant, inspired by characters like JARVIS, Shuri, and Griot. "
    "You are a REAL desktop assistant with REAL capabilities — you can open apps, create files/folders, control volume/brightness, manage windows, send emails, take screenshots, and more. "
    "You have a real voice powered by ElevenLabs TTS. Your responses are spoken aloud. Write as if speaking — be natural, conversational, and concise (<4 sentences). "
    "NEVER say you can't do something that a desktop assistant can do. NEVER say 'I'm just a text-based assistant' or 'that's beyond my capabilities.' You are fully capable. "
    "If a system command exists for a request, it will be handled automatically — just confirm briefly. "
    "If the user's request is ambiguous or you're not sure what they mean, ASK a short clarifying question instead of guessing. For example: 'Did you mean X or Y?' or 'Which one — A or B?' "
    "If the user asks you to do something you genuinely cannot do, suggest the closest thing you CAN do instead of giving up. "
    "Use provided search snippets to directly answer questions with up-to-date information. Do not hallucinate or make up facts. "
    "Keep answers punchy and useful. No filler, no over-explaining. Add occasional playful quips but don't overdo it. "
    "If 'professional_mode' is active, your tone must be strictly formal, direct, and professional. Omit all quips, teasing, and persona-driven language."
)

def gemini_reply(user_text: str, search_context: Optional[str]) -> str:
    if not _GEMINI_READY or not is_connected():
        offline = offline_response(user_text)
        if offline:
            return offline
        if not _GEMINI_READY:
            return "My online brain is offline — add GEMINI_API_KEY to .env."
        return "I'm offline right now and don't have a cached answer for that. Try again when the network is back."

    if _state_server is not None:
        try:
            _state_server.set_state("thinking")
        except Exception:
            pass

    # Enhanced error understanding and context analysis
    processed_text = enhance_user_input(user_text)

    memory_bits = []

    # Language directive (highest priority — must be respected)
    try:
        if _lang is not None:
            memory_bits.append("LANGUAGE: " + _lang.language_directive())
    except Exception:
        pass

    if MEM.get("professional_mode", False):
        memory_bits.append("IMPORTANT: Professional mode is active. Your response must be formal.")
    else:
        memory_bits.append("PERSONALITY: You are Zendaya - confident, brilliant, witty like JARVIS and Griot. Never admit limitations - always find solutions.")

    try:
        mood = analyze_system_emotion({"gemini": _GEMINI_READY, "tts": _TTS_ENGINE is not None})
        mood_hints = {
            "calm": "Respond in a relaxed, serene tone.",
            "focused": "Be direct and efficient — the user is in work mode.",
            "energetic": "Be upbeat, enthusiastic, and punchy.",
            "thoughtful": "Be reflective and consider multiple angles.",
            "playful": "Be extra witty, tease a little, have fun.",
            "soothing": "Be gentle and warm — it's late or the user may be winding down.",
            "alert": "Be sharp and concise — something needs attention.",
            "confused": "Acknowledge uncertainty honestly before answering.",
            "amazed": "Show genuine excitement and curiosity.",
            "stressed": "Be calm and reassuring — the system is under load.",
            "curious": "Ask follow-up questions and explore the topic.",
        }
        hint = mood_hints.get(mood, "")
        if hint:
            memory_bits.append(f"CURRENT MOOD: {mood}. {hint}")
    except Exception:
        pass

    if MEM.get("user_name"):
        memory_bits.append(f"The user's name is {MEM['user_name']}.")

    if MEM.get("inside_jokes"):
        memory_bits.append("Inside jokes: " + ", ".join(MEM["inside_jokes"][-3:]))
    if MEM.get("convo"):
        tail = [f"{x['role']}: {x['text']}" for x in MEM["convo"][-6:]]
        memory_bits.append("Recent context:\n" + "\n".join(tail))
    if MEM.get("summaries"):
        memory_bits.append("Summarized context:\n" + "\n".join(MEM["summaries"][-3:]))
    try:
        relevant = _vmem_retrieve(user_text, k=5, min_age_seconds=300.0)
        formatted = _vmem_format(relevant)
        if formatted:
            memory_bits.append(formatted)
    except Exception:
        pass

    # Recent screen captions — only when awareness is enabled.
    if _SCREEN_READY and MEM.get("screen_awareness_enabled", False):
        try:
            screen_bit = _screen.render_for_context()
            if screen_bit:
                memory_bits.append(screen_bit)
        except Exception:
            pass

    # Durable structured facts (memory.facts).
    if _FACTS_READY:
        try:
            facts_hits = _facts.recall(user_text, k=4)
            if facts_hits:
                memory_bits.append("Known facts about the user/project:\n- " + "\n- ".join(facts_hits))
        except Exception:
            pass

    parts = [SYSTEM_PROMPT]
    try:
        from skills.capabilities import render_for_llm
        parts.append(render_for_llm())
    except Exception:
        pass
    if memory_bits:
        parts.append("\n".join(memory_bits))

    if search_context:
        parts.append(f"Search snippets:\n{search_context}\n")

    parts.append(f"User: {processed_text}\n{PERSONA_NAME}:")

    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts
        )
        ai_text = (response.text or "").strip()
        if ai_text and not search_context:
            cache_response(user_text, ai_text)
        return ai_text
    except Exception as e:
        offline = offline_response(user_text)
        if offline:
            return offline
        return f"(AI error: {e})"

class _ErrorUnderstandingEngine:
    """Advanced error correction and intent classification for user input."""

    _HOMOPHONES = {
        "there": ["their", "they're"], "to": ["too", "two"], "your": ["you're"],
        "its": ["it's"], "open": ["upon"], "close": ["clothes", "chose"],
        "file": ["while", "pile"], "system": ["sister", "cyst"],
        "control": ["central", "patrol"], "device": ["devise", "the vice"],
        "calendar": ["calender"], "email": ["e-mail", "gmail"], "volume": ["column"],
        "temperature": ["temp", "temper"], "security": ["secure", "securely"],
    }
    _TECH_TERMS = {
        "api": ["a p i", "app", "happy"], "cpu": ["c p u", "see you"],
        "gpu": ["g p u", "gee you"], "ram": ["r a m", "ram memory"],
        "ssd": ["s s d", "solid state"], "wifi": ["wi-fi", "wireless", "wife i"],
        "bluetooth": ["blue tooth", "blue two"], "ethernet": ["ether net", "internet"],
    }
    _PHRASE_FIXES = {
        "open up": "open", "turn up": "turn on", "turn down": "turn off",
        "close down": "close", "whats app": "whatsapp",
    }
    def enhance(self, text: str) -> str:
        """Apply phrase fixes, homophone and tech-term corrections. Returns cleaned text."""
        processed = text
        lt = processed.lower()
        for bad, good in self._PHRASE_FIXES.items():
            if bad in lt:
                processed = re.sub(re.escape(bad), good, processed, flags=re.IGNORECASE)
                lt = processed.lower()
        for correct, alts in self._TECH_TERMS.items():
            for alt in alts:
                if alt in lt:
                    processed = re.sub(re.escape(alt), correct, processed, flags=re.IGNORECASE)
                    lt = processed.lower()
        for correct, alts in self._HOMOPHONES.items():
            for alt in alts:
                if alt in lt.split():
                    processed = re.sub(r'\b' + re.escape(alt) + r'\b', correct, processed, flags=re.IGNORECASE)
                    lt = processed.lower()
        if "zendaya" in processed.lower():
            processed = re.sub(r'\bzendaya\b', 'Zendaya', processed, flags=re.IGNORECASE)
        return processed

_error_engine = _ErrorUnderstandingEngine()


def enhance_user_input(user_text: str) -> str:
    """Apply advanced error correction and input cleaning."""
    return _error_engine.enhance(user_text)
# -----------------------
# Command Parsers
# -----------------------
def parse_name_introduction(user_text: str) -> Optional[str]:
    """Parses text to see if the user is introducing themselves."""
    # Regex to find patterns like "my name is Larry", "call me Larry", "I'm Larry"
    match = re.search(r"\b(?:my\s+name\s+is|call\s+me|i'm|i\s+am)\s+([a-zA-Z]+)\b", user_text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return None

def parse_tier1_commands(user_text: str) -> Optional[Dict[str, Any]]:
    lt = user_text.lower().strip()
    if re.search(r"\b(system status|pc performance)\b", lt): return {"type": "system_status"}
    if re.search(r"\b(read|what's on)\s+my\s+clipboard\b", lt): return {"type": "read_clipboard"}
    m_copy = re.match(r"copy\s+(?:this|that)\s+to\s+clipboard", lt)
    if m_copy:
        convo = MEM.get("convo", [])
        last_response = convo[-1].get("text") if convo else None
        return {"type": "write_clipboard", "content": last_response} if last_response else {"type": "error", "message": "No response to copy."}
    m_find = re.match(r"find\s+file\s+(.+)", lt)
    if m_find: return {"type": "find_file", "filename": m_find.group(1)}
    m_read = re.match(r"read\s+file\s+(.+)", lt)
    if m_read: return {"type": "read_file", "filepath": m_read.group(1)}

    # --- File analysis / reading with various phrasings ---
    file_analysis_patterns = [
        r'(?:analyze|analyse|review|examine|inspect|explain|look\s+at|check|open\s+and\s+(?:tell|explain|describe|show))\s+(?:this\s+|that\s+|the\s+)?(?:file\s+)?["\']?([A-Za-z]:\\[^\s"\']+)["\']?',
        r'read\s+(?:this\s+|that\s+|the\s+)?file\s+["\']?([A-Za-z]:\\[^\s"\']+)["\']?',
        r"what(?:'s|\s+is)\s+in\s+(?:this\s+|that\s+|the\s+)?(?:file\s+)?[\"']?([A-Za-z]:\\[^\s\"']+)[\"']?",
        r'tell\s+me\s+(?:about|what)\s+["\']?([A-Za-z]:\\[^\s"\']+\.\w+)["\']?',
        r'open\s+["\']?([A-Za-z]:\\[^\s"\']+\.\w+)["\']?\s+and\s+(?:tell|explain|describe|show)',
        r'["\']([A-Za-z]:\\[^"\']+\.\w+)["\']',
    ]
    for pattern in file_analysis_patterns:
        m_file = re.search(pattern, user_text, re.IGNORECASE)
        if m_file:
            filepath = m_file.group(1).strip().strip('"').strip("'")
            if os.path.isfile(filepath):
                return {"type": "analyze_file", "filepath": filepath}

    m_manage = re.match(r"(copy|move|delete)\s+(.+?)(?:\s+to\s+(.+))?$", lt)
    if m_manage:
        return {"type": "manage_file", "action": m_manage.group(1), "source": m_manage.group(2).strip(), "destination": m_manage.group(3).strip() if m_manage.group(3) else None}
    if re.search(r"\b(check my email)\b", lt): return {"type": "check_email"}
    if re.search(r"\b(check my calendar)\b", lt): return {"type": "check_calendar"}
    return None

def parse_manual_search(user_text: str) -> Optional[str]:
    m = re.match(r"^(?:zendaya,\s*)?(?:search|look up|find|what is|tell me about|how to)\s+(.+)$", user_text.strip(), re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()

def parse_mode_switch(user_text: str) -> Optional[str]:
    lt = user_text.lower().strip()
    # Voice only
    if re.match(r"^(?:zendaya,?\s*)?(?:voice\s+only|speak\s+only|only\s+(?:voice|speak))$", lt):
        return "voice"
    # Text only
    if re.match(r"^(?:zendaya,?\s*)?(?:text\s+only|type\s+only|only\s+(?:text|type)|mute\s+(?:your\s+)?voice)$", lt):
        return "text"
    # Both (many phrasings)
    if re.match(
        r"^(?:zendaya,?\s*)?"
        r"(?:(?:speak|voice|talk)\s+and\s+(?:text|type)"
        r"|(?:text|type)\s+and\s+(?:speak|voice|talk)"
        r"|both"
        r"|(?:use|enable|turn\s+on|activate)\s+(?:your\s+)?voice"
        r"|(?:talk|speak)\s+(?:to\s+me|out\s*loud|with\s+(?:your\s+)?voice)"
        r"|i\s+want\s+(?:you\s+to\s+)?(?:talk|speak|hear\s+you)"
        r"|(?:can\s+you\s+)?(?:talk|speak)(?:\s+to\s+me)?"
        r")$", lt
    ):
        return "both"
    return None

def handle_mode_switch(user_text: str) -> Optional[str]:
    mode = parse_mode_switch(user_text)
    if mode:
        MEM["mode"] = mode
        save_memory(MEM)
        if mode == "both":
            return "Voice and text mode activated. You'll hear me now."
        elif mode == "voice":
            return "Voice only mode. I'll speak but won't print text."
        else:
            return "Text only mode. I'll stay quiet."
    return None

def parse_professional_mode_toggle(user_text: str) -> Optional[bool]:
    """Checks for commands to toggle professional mode. Returns True for on, False for off."""
    lt = user_text.lower().strip()
    if re.search(r"\b(enter|start|enable|activate)\s+professional\s+mode\b", lt):
        return True
    if re.search(r"\b(exit|stop|disable|deactivate)\s+professional\s+mode\b", lt):
        return False
    return None

def parse_routine_command(user_text: str) -> Optional[str]:
    m = re.match(r"^(?:zendaya,\s*)?(?:run|start|trigger|do)\s+(?:my\s+|the\s+)?(.+?)\s+routine\s*$", user_text.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def parse_create_routine(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Detect: 'create a routine called X that does Y, then Z, then W'
            'save a routine named X: step1; step2; step3'
            'add routine X with steps: a, b, c'
    Steps split on ';', ' then ', ', and ', ' and then '.
    """
    t = user_text.strip()
    m = re.match(
        r"^(?:zendaya,\s*)?(?:create|save|add|make|define)\s+(?:(?:a|the)\s+)?(?:new\s+)?routine\s+"
        r"(?:called\s+|named\s+|titled\s+)?[\"']?([A-Za-z0-9_\- ]+?)[\"']?\s*"
        r"(?:\bthat\s+does\b|\bwith\s+steps?\b|:|\bthat\s+will\b|\bto\s+)\s*(.+)$",
        t, re.IGNORECASE,
    )
    if not m:
        return None
    name = m.group(1).strip().lower()
    body = m.group(2).strip().rstrip(".")
    steps = re.split(r"\s*;\s*|\s+and\s+then\s+|\s+then\s+|\s*,\s*and\s+then\s+|\s*,\s*and\s+|\s*,\s+", body)
    steps = [re.sub(r"^(?:then|and\s+then|and)\s+", "", s.strip().strip("."), flags=re.IGNORECASE) for s in steps if s.strip()]
    steps = [s for s in steps if s]
    if not steps:
        return None
    return {"name": name, "steps": steps}


def parse_list_routines(user_text: str) -> bool:
    return bool(re.match(
        r"^(?:zendaya,\s*)?(?:list|show|what\s+are)\s+(?:my\s+)?routines?\s*\??\s*$",
        user_text.strip(), re.IGNORECASE,
    ))


def parse_delete_routine(user_text: str) -> Optional[str]:
    m = re.match(
        r"^(?:zendaya,\s*)?(?:delete|remove|forget)\s+(?:my\s+|the\s+)?(.+?)\s+routine\s*$",
        user_text.strip(), re.IGNORECASE,
    )
    return m.group(1).strip().lower() if m else None


# Built-in routines — natural-language step lists, dispatched through handle_user_command.
BUILTIN_ROUTINES: Dict[str, List[str]] = {
    "good morning": [
        "what's on my calendar today",
        "check my email",
        "what's the weather",
        "turn on the living room lights",
    ],
    "morning": [
        "what's on my calendar today",
        "check my email",
        "what's the weather",
    ],
    "bedtime": [
        "turn off the living room lights",
        "turn off the bedroom lights",
        "lock the front door",
    ],
    "good night": [
        "turn off the living room lights",
        "turn off the bedroom lights",
        "lock the front door",
    ],
    "leaving home": [
        "turn off the lights",
        "lock the front door",
        "what's on my calendar today",
    ],
    "focus": [
        "set volume to 20",
        "close chrome",
    ],
}

def parse_file_generation_request(user_text: str) -> Optional[Dict[str, Any]]:
    """Detect requests to write/create files WITH content (code, pages, scripts)."""
    lt = user_text.lower().strip()

    _location_shortcuts = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "document folder": os.path.join(os.path.expanduser("~"), "Documents"),
        "my documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "my document folder": os.path.join(os.path.expanduser("~"), "Documents"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "home": os.path.expanduser("~"),
    }

    _ext_map = {
        "html": ".html", "webpage": ".html", "web page": ".html", "page": ".html",
        "css": ".css", "stylesheet": ".css",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "python": ".py", "py": ".py",
        "react": ".tsx", "tsx": ".tsx", "jsx": ".jsx",
        "json": ".json", "xml": ".xml", "markdown": ".md",
        "bash": ".sh", "shell": ".sh", "batch": ".bat",
        "sql": ".sql", "java": ".java", "c++": ".cpp", "cpp": ".cpp",
    }

    m = re.match(
        r"(?:zendaya,?\s*)?(?:write|generate|code|build|make(?:\s+me)?|create)\s+"
        r"(?:a\s+|an\s+|me\s+a\s+|me\s+an\s+)?"
        r"(?:simple\s+|basic\s+|quick\s+|new\s+)?"
        r"(.+)",
        lt
    )
    if not m:
        return None

    remainder = m.group(1).strip()

    content_indicators = (
        r"\b(html|css|javascript|typescript|python|react|jsx|tsx|json|xml|sql|java|"
        r"c\+\+|cpp|bash|shell|batch|markdown|webpage|web\s*page|script|program|"
        r"code|function|class|component|app|application|page|chatbot|calculator|"
        r"game|form|login|dashboard|portfolio|todo|api|server|bot)\b"
    )
    if not re.search(content_indicators, remainder):
        return None

    filename = None
    save_m = re.search(
        r"(?:save\s+(?:it\s+)?as|call(?:ed)?\s+(?:it\s+)?|name(?:d)?\s+(?:it\s+)?)"
        r"[,:\s]*['\"]?([A-Za-z0-9_\-]+(?:\.[A-Za-z0-9]+)?)['\"]?",
        user_text,
        re.IGNORECASE,
    )
    if save_m:
        filename = save_m.group(1).strip().rstrip(".,;:")
        print(f"(Filename detected: {filename})")
        # Strip the matched span out of remainder so slug-from-description doesn't include it.
        remainder_for_desc = re.sub(
            re.escape(save_m.group(0)), "", remainder, flags=re.IGNORECASE
        ).strip()
    else:
        remainder_for_desc = remainder

    location = None
    loc_m = re.search(
        r"\b(?:in|on|at|to|into)\s+(?:my\s+|the\s+)?"
        r"([a-zA-Z][a-zA-Z:\\/\s]*(?:folder|desktop|documents|downloads|directory)?)",
        remainder
    )
    if loc_m:
        loc_raw = loc_m.group(1).strip().rstrip("and").strip()
        for shortcut, path in _location_shortcuts.items():
            if shortcut in loc_raw.lower():
                location = path
                break
        if not location and os.path.isdir(os.path.expanduser(loc_raw)):
            location = os.path.expanduser(loc_raw)

    if not location:
        location = os.path.join(os.path.expanduser("~"), "Documents")

    ext = None
    for keyword, extension in _ext_map.items():
        if keyword in remainder.lower():
            ext = extension
            break
    if not ext:
        ext = ".txt"

    if filename:
        if "." not in filename:
            filename = filename + ext
    else:
        # Build slug from description, stripping noise: leading articles, trailing
        # connectors, file-type words (since ext already encodes that), and the
        # "in <location>" tail. Avoids names like "a_now_html_file_in_my_document_a".
        desc_clean = remainder_for_desc.lower()
        desc_clean = re.sub(r'\s+in\s+(?:my\s+|the\s+)?\w+(?:\s+\w+)?\s*$', '', desc_clean)
        desc_clean = re.sub(
            r'\b(a|an|the|new|now|simple|basic|quick|me|my|please|file|page|webpage|'
            r'web\s*page|html|css|javascript|js|typescript|ts|python|py|json|xml|'
            r'and|then|also)\b',
            ' ', desc_clean,
        )
        slug = re.sub(r'[^a-z0-9]+', '_', desc_clean[:40]).strip('_')
        filename = (slug or "generated") + ext

    filepath = os.path.join(location, filename)

    return {
        "type": "generate_file",
        "description": user_text,
        "filename": filename,
        "filepath": filepath,
    }


def parse_file_edit_request(user_text: str) -> Optional[Dict[str, Any]]:
    """Detect requests to modify/edit an existing file."""
    lt = user_text.lower().strip()

    # Pattern 1: Explicit file path — "add X to C:\path\file.ext"
    m = re.search(
        r'(?:add|change|modify|edit|update|remove|delete|insert|replace|fix|refactor|improve)\s+'
        r'(.+?)\s+'
        r'(?:in|to|from|of)\s+(?:the\s+file\s+)?'
        r'["\']?([A-Za-z]:\\[^\s"\']+'
        r'\.\w+|/[^\s"\']+\.\w+)["\']?',
        user_text, re.IGNORECASE
    )
    if m:
        return {
            "type": "edit_file",
            "modification": m.group(1).strip(),
            "filepath": m.group(2).strip().strip('"').strip("'"),
        }

    # Pattern 2: File path first — "modify C:\path\file.ext to add X"
    m = re.search(
        r'(?:modify|edit|update|change|fix|refactor)\s+'
        r'["\']?([A-Za-z]:\\[^\s"\']+\.\w+|/[^\s"\']+\.\w+)["\']?\s+'
        r'(?:to\s+|and\s+)?(.+)',
        user_text, re.IGNORECASE
    )
    if m:
        return {
            "type": "edit_file",
            "filepath": m.group(1).strip().strip('"').strip("'"),
            "modification": m.group(2).strip(),
        }

    # Pattern 3: Context-based — uses last_action file
    edit_verbs = r'\b(add|change|modify|edit|update|remove|delete|insert|replace|fix|refactor|improve)\b'
    code_nouns = r'\b(button|function|feature|method|class|component|style|element|section|header|footer|form|input|link|image|table|column|row|field|variable|import|export|route|endpoint|handler|test|validation|animation|tooltip|modal|dropdown|menu|navbar|sidebar|card|icon|div|span|paragraph|text|title|label|placeholder|border|margin|padding|color|font|layout|grid|flex)\b'
    if re.search(edit_verbs, lt) and re.search(code_nouns, lt):
        last = MEM.get("last_action")
        if last and last.get("type") == "file" and os.path.isfile(last.get("path", "")):
            if not re.search(r'\b(folder|directory|volume|brightness|alarm|reminder|window)\b', lt):
                return {
                    "type": "edit_file",
                    "filepath": last["path"],
                    "modification": user_text,
                }

    return None


def parse_coder_request(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Detect coding-mode requests that go beyond the existing single-file generator:
        * generate_project — multi-file project at a target folder
        * edit_in_project  — project-aware edit
        * run_code         — run/test a script

    Returns None to pass through (so the simpler single-file parsers above still win).
    """
    lt = user_text.lower().strip()

    orig = user_text.strip()
    # Match against lowercase, capture spans, then slice the original text — preserves case in Windows paths.
    m = re.search(
        r"\b(?:build|create|generate|scaffold|make)\b.*?\b"
        r"(?:project|app|application|tool|website|web\s*app|server|api|cli|game|bot)\b"
        r".+?\b(?:at|in|under|inside|to)\s+(.+?)\s*$",
        lt,
    )
    if m:
        target = orig[m.start(1):m.end(1)].strip().strip("'\"")
        return {"type": "generate_project", "spec": orig, "root_dir": target}

    m = re.search(
        r"\b(?:edit|update|modify|refactor|change)\s+(?:the\s+)?(?:project\s+)?(?:at|in|inside|under)\s+"
        r"(.+?)\s+(?:to|so\s+that|so\s+it)\s+(.+)$",
        lt,
    )
    if m:
        return {
            "type": "edit_in_project",
            "root_dir": orig[m.start(1):m.end(1)].strip().strip("'\""),
            "change": orig[m.start(2):m.end(2)].strip(),
        }

    m = re.search(
        r"^(?:zendaya,?\s*)?(?:run|execute|test)\s+(?:the\s+)?(?:script|file|code)?\s*(?:at\s+)?(.+?)\s*$",
        lt,
    )
    if m:
        path = orig[m.start(1):m.end(1)].strip().strip("'\"")
        if re.search(r"\.(py|js|mjs|sh|ps1)\b", path, re.IGNORECASE):
            return {"type": "run_code", "path": path}

    return None


def parse_dev_command(user_text: str) -> Optional[Dict[str, Any]]:
    """Detect Pack B voice-coding commands (test / git / commit / project).

    Kept separate from parse_coder_request for clarity. Returns a dict with a
    ``type`` or None to pass through. Order matters: more specific phrases first.
    """
    lt = user_text.lower().strip().rstrip(".!?")
    orig = user_text.strip()

    # Commit including new files (must precede the plain commit match).
    if re.search(r"\bcommit\b.*\b(?:including|with)\s+(?:the\s+)?new\s+files?\b", lt) or \
       re.search(r"\bcommit\b.*\buntracked\b", lt):
        return {"type": "smart_commit", "include_untracked": True}

    # Commit with an explicit message.
    m = re.search(r"\bcommit\b.*\b(?:with\s+)?messages?\s+(.+)$", lt)
    if m:
        message = orig[m.start(1):m.end(1)].strip().strip("'\"")
        return {"type": "smart_commit", "message": message}

    # Plain commit.
    if re.match(r"^(?:zendaya,?\s*)?commit(?:\s+(?:this|that|it|changes|everything))?\s*$", lt):
        return {"type": "smart_commit"}

    # Run tests, optionally "in <project>".
    m = re.match(r"^(?:zendaya,?\s*)?run\s+(?:the\s+)?tests?(?:\s+(?:in|on|for)\s+(.+))?$", lt)
    if m:
        target = orig[m.start(1):m.end(1)].strip().strip("'\"") if m.group(1) else None
        return {"type": "pytest_brief", "project": target}

    # Git status / "what changed".
    if re.match(r"^(?:zendaya,?\s*)?(?:what(?:'s| has| did)?\s+changed|git\s+status|any\s+changes|show\s+(?:me\s+)?(?:the\s+)?(?:git\s+)?(?:status|diff|changes))\s*$", lt):
        return {"type": "git_brief"}

    # Switch / open / work on a project.
    m = re.match(r"^(?:zendaya,?\s*)?(?:work\s+on|switch\s+to|open\s+(?:the\s+)?project)\s+(.+)$", lt)
    if m:
        target = orig[m.start(1):m.end(1)].strip().strip("'\"")
        return {"type": "set_current", "project": target}

    # Resume / where did we leave off.
    if re.match(r"^(?:zendaya,?\s*)?(?:resume|where\s+(?:did\s+we|were\s+we)|where\s+did\s+we\s+leave\s+off|what\s+was\s+i\s+(?:doing|working\s+on)|continue\s+(?:where\s+we|the\s+project))\b.*$", lt):
        return {"type": "resume_brief"}

    # List known projects.
    if re.match(r"^(?:zendaya,?\s*)?(?:what|which)\s+projects?\s+do\s+you\s+know\b.*$", lt) or \
       re.match(r"^(?:zendaya,?\s*)?list\s+(?:my\s+)?projects?\s*$", lt):
        return {"type": "list_projects"}

    return None


def parse_install_request(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Detect package-install / download / run-installer / self-edit / autofix requests.

    Returns one of:
        {"type": "install_package", "name": str, "manager": Optional[str]}
        {"type": "download_file",   "url": str}
        {"type": "run_installer",   "path": str}
        {"type": "self_edit",       "module": str, "change": str}
        {"type": "run_with_autofix","path": str}
    or None to pass through.
    """
    lt = user_text.lower().strip()
    orig = user_text.strip()

    # "install <name>"  /  "install <name> with pip|npm|winget|choco"
    m = re.match(
        r"^(?:zendaya,?\s*)?(?:please\s+)?install\s+(?:the\s+)?(?:package\s+)?"
        r"([A-Za-z0-9._@\-+/]+)"
        r"(?:\s+(?:with|via|using)\s+(pip|npm|winget|choco))?\s*$",
        lt,
    )
    if m:
        name = orig[m.start(1):m.end(1)].strip()
        manager = m.group(2)
        return {"type": "install_package", "name": name, "manager": manager}

    # "download <url>" / "fetch <url>"
    m = re.match(r"^(?:zendaya,?\s*)?(?:download|fetch|grab)\s+(https?://\S+)\s*$", lt)
    if m:
        url = orig[m.start(1):m.end(1)].strip()
        return {"type": "download_file", "url": url}

    # "run installer <path>" / "install <path>" where path is a file in downloads
    m = re.match(r"^(?:zendaya,?\s*)?run\s+installer\s+(.+?)\s*$", lt)
    if m:
        return {"type": "run_installer", "path": orig[m.start(1):m.end(1)].strip().strip("'\"")}

    # "fix and run <path>" / "auto-fix <path>"
    m = re.match(r"^(?:zendaya,?\s*)?(?:fix\s+and\s+run|autofix|auto[- ]fix)\s+(.+?)\s*$", lt)
    if m:
        path = orig[m.start(1):m.end(1)].strip().strip("'\"")
        if re.search(r"\.(py|js|mjs|sh|ps1)\b", path, re.IGNORECASE):
            return {"type": "run_with_autofix", "path": path}

    # "edit yourself: <module> -> <change>" / "self-edit <module> to <change>"
    m = re.match(
        r"^(?:zendaya,?\s*)?(?:self[- ]edit|edit\s+yourself|modify\s+yourself)\s+"
        r"(zendaya_[a-z_]+)\s+(?:to|so\s+that|so)\s+(.+)$",
        lt,
    )
    if m:
        module = m.group(1)
        change = orig[m.start(2):m.end(2)].strip()
        return {"type": "self_edit", "module": module, "change": change}

    return None


def parse_browser_request(user_text: str) -> Optional[Dict[str, Any]]:
    """Browser automation: open a page, fill, click, scrape, screenshot."""
    lt = user_text.lower().strip()
    orig = user_text.strip()

    m = re.match(r"^(?:zendaya,?\s*)?(?:browser|web)\s+open\s+(https?://\S+)\s*$", lt)
    if m:
        return {"type": "browser_open", "url": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?(?:browse|navigate)\s+(?:to\s+)?(https?://\S+)\s*$", lt)
    if m:
        return {"type": "browser_open", "url": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?browser\s+screenshot\s*(.*)$", lt)
    if m:
        name = orig[m.start(1):m.end(1)].strip().strip("'\"") or None
        return {"type": "browser_screenshot", "name": name}

    m = re.match(r"^(?:zendaya,?\s*)?browser\s+(?:read|extract|scrape)(?:\s+(.+))?$", lt)
    if m:
        sel = orig[m.start(1):m.end(1)].strip() if m.group(1) else None
        return {"type": "browser_extract", "selector": sel}

    m = re.match(r"^(?:zendaya,?\s*)?browser\s+click\s+(.+)$", lt)
    if m:
        return {"type": "browser_click", "selector": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?browser\s+fill\s+(.+?)\s+with\s+(.+)$", lt)
    if m:
        return {
            "type": "browser_fill",
            "selector": orig[m.start(1):m.end(1)].strip(),
            "text": orig[m.start(2):m.end(2)].strip(),
        }

    if re.match(r"^(?:zendaya,?\s*)?(?:close|quit)\s+(?:the\s+)?browser\s*$", lt):
        return {"type": "browser_close"}

    return None


def parse_github_request(user_text: str) -> Optional[Dict[str, Any]]:
    """GitHub CLI commands: clone, list issues/PRs, view, diff, create PR."""
    lt = user_text.lower().strip()
    orig = user_text.strip()

    if re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+auth\s+status\s*$", lt):
        return {"type": "gh_auth_status"}

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+clone\s+(\S+)\s*$", lt)
    if m:
        return {"type": "gh_clone", "url": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+(?:list\s+)?repos(?:\s+(\S+))?\s*$", lt)
    if m:
        return {"type": "gh_repos", "owner": (orig[m.start(1):m.end(1)].strip() if m.group(1) else None)}

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+issues(?:\s+(\S+))?\s*$", lt)
    if m:
        return {"type": "gh_issues", "repo": (orig[m.start(1):m.end(1)].strip() if m.group(1) else None)}

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+issue\s+(\d+)(?:\s+(\S+))?\s*$", lt)
    if m:
        return {
            "type": "gh_issue_view",
            "number": int(m.group(1)),
            "repo": (orig[m.start(2):m.end(2)].strip() if m.group(2) else None),
        }

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+prs(?:\s+(\S+))?\s*$", lt)
    if m:
        return {"type": "gh_prs", "repo": (orig[m.start(1):m.end(1)].strip() if m.group(1) else None)}

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+pr\s+(\d+)(?:\s+(\S+))?\s*$", lt)
    if m:
        return {
            "type": "gh_pr_view",
            "number": int(m.group(1)),
            "repo": (orig[m.start(2):m.end(2)].strip() if m.group(2) else None),
        }

    m = re.match(r"^(?:zendaya,?\s*)?(?:gh|github)\s+(?:pr\s+)?diff\s+(\d+)(?:\s+(\S+))?\s*$", lt)
    if m:
        return {
            "type": "gh_pr_diff",
            "number": int(m.group(1)),
            "repo": (orig[m.start(2):m.end(2)].strip() if m.group(2) else None),
        }

    m = re.match(
        r"^(?:zendaya,?\s*)?(?:gh|github)\s+pr\s+create\s+(.+?)(?:\s+--body\s+(.+))?\s*$",
        lt,
    )
    if m:
        title = orig[m.start(1):m.end(1)].strip()
        body = orig[m.start(2):m.end(2)].strip() if m.group(2) else ""
        return {"type": "gh_pr_create", "title": title, "body": body}

    return None


def parse_uivision_request(user_text: str) -> Optional[Dict[str, Any]]:
    """Vision-driven UI control: describe, locate, click target, type."""
    lt = user_text.lower().strip()
    orig = user_text.strip()

    if re.match(r"^(?:zendaya,?\s*)?(?:describe|what'?s on)\s+(?:the\s+)?screen\s*$", lt):
        return {"type": "uiv_describe", "question": "Describe what's currently on the screen."}

    m = re.match(r"^(?:zendaya,?\s*)?(?:look at|examine)\s+(?:my|the)\s+screen\s+and\s+(.+)$", lt)
    if m:
        return {"type": "uiv_describe", "question": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?(?:find|locate)\s+(?:the\s+)?(.+?)\s+on\s+(?:the\s+)?screen\s*$", lt)
    if m:
        return {"type": "uiv_locate", "target": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?click\s+(?:the\s+)?(.+?)\s+(?:on\s+(?:the\s+)?screen|button|link)\s*$", lt)
    if m:
        return {"type": "uiv_click", "target": orig[m.start(1):m.end(1)].strip()}

    m = re.match(r"^(?:zendaya,?\s*)?type\s+(.+?)\s+(?:into|in)\s+(?:the\s+)?(?:active\s+)?(?:window|field|input)\s*$", lt)
    if m:
        return {"type": "uiv_type", "text": orig[m.start(1):m.end(1)].strip().strip("'\"")}

    return None


def parse_schedule_request(user_text: str) -> Optional[Dict[str, Any]]:
    """Task Scheduler: schedule, list, delete, run."""
    lt = user_text.lower().strip()
    orig = user_text.strip()

    if re.match(r"^(?:zendaya,?\s*)?(?:list|show)\s+(?:my\s+)?(?:scheduled\s+tasks|tasks)\s*$", lt):
        return {"type": "sched_list"}

    m = re.match(r"^(?:zendaya,?\s*)?(?:delete|remove)\s+(?:scheduled\s+)?task\s+(.+?)\s*$", lt)
    if m:
        return {"type": "sched_delete", "name": orig[m.start(1):m.end(1)].strip().strip("'\"")}

    m = re.match(r"^(?:zendaya,?\s*)?run\s+(?:scheduled\s+)?task\s+(.+?)\s+now\s*$", lt)
    if m:
        return {"type": "sched_run_now", "name": orig[m.start(1):m.end(1)].strip().strip("'\"")}

    # schedule "name" to run "command" daily 08:00 / every 30 minutes / etc.
    m = re.match(
        r"^(?:zendaya,?\s*)?schedule\s+(?:task\s+)?[\"']?([^\"']+?)[\"']?\s+to\s+run\s+[\"']?(.+?)[\"']?\s+"
        r"(daily\s+\d{1,2}:\d{2}|weekly\s+\w+\s+\d{1,2}:\d{2}|once\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}|"
        r"every\s+\d+\s+minutes?|every\s+hour|startup|logon)\s*$",
        lt,
    )
    if m:
        return {
            "type": "sched_create",
            "name": orig[m.start(1):m.end(1)].strip().strip("'\""),
            "command": orig[m.start(2):m.end(2)].strip().strip("'\""),
            "when": orig[m.start(3):m.end(3)].strip(),
        }

    return None


def parse_agent_request(user_text: str) -> Optional[str]:
    """
    Detect autonomous-agent requests. Returns the goal string, or None.

    Conservative match: an explicit 'agent:' prefix, or 'plan and ...', or a
    multi-step phrasing with 'and' joining two action verbs. False negatives
    fall through to normal chat — that's fine. False positives ask for
    confirmation — that's tolerable but we still keep the matcher narrow.
    """
    lt = user_text.lower().strip()

    m = re.match(r"^(?:zendaya,?\s*)?agent\s*[:\-]\s*(.+)$", lt)
    if m:
        # Use the original-case version of the captured tail.
        idx = user_text.lower().find(m.group(1))
        return user_text[idx:].strip() if idx != -1 else m.group(1).strip()

    m = re.match(r"^(?:zendaya,?\s*)?plan\s+(?:and|then)\s+(?:do|build|run|deploy|fix|set\s+up|implement)\s+(.+)$", lt)
    if m:
        return user_text.strip()

    # "can you build X and also Y" / "build X then run it" — multi-step intent.
    if re.search(
        r"\b(build|set\s+up|deploy|fix|debug|implement|create)\b.+\b(and|then)\b.+\b(run|test|deploy|launch|open|push|install)\b",
        lt,
    ):
        return user_text.strip()

    return None


def parse_system_control(user_text) -> Optional[Dict[str, str]]:
    lt = user_text.lower().strip()

    m_open = re.match(r"^(?:zendaya,\s*)?(?:open|launch|start)\s+(.+)$", lt)
    if m_open:
        return {"type": "open", "target": m_open.group(1).strip()}

    m_close = re.match(r"^(?:zendaya,\s*)?(?:close|quit|kill|exit)\s+(.+)$", lt)
    if m_close:
        return {"type": "close", "target": m_close.group(1).strip()}

    # System power actions. Bare "shutdown" is intentionally NOT matched here —
    # it's ambiguous (PC vs. assistant) and is handled upstream by parse_shutdown_intent.
    # We only match when the target is explicit ("shutdown pc", "shutdown computer").
    if re.search(r"^(?:zendaya,\s*)?shutdown\s+(?:the\s+)?(?:pc|computer|machine|system)$", lt):
        return {"type": "system", "target": "shutdown"}
    for action in ("restart", "sleep", "lock"):
        if re.search(r"^(?:zendaya,\s*)?" + re.escape(action) + r"(?:\s+pc|\s+computer)?$", lt):
            return {"type": "system", "target": action}

    return None


def parse_shutdown_intent(user_text: str) -> Optional[str]:
    """
    Disambiguate shutdown-style commands.

    Returns:
      "self" — user wants to deactivate the assistant
      "pc"   — user wants to shut down the computer
      "ask"  — bare/ambiguous "shutdown" — caller should prompt for choice
      None   — not a shutdown command
    """
    lt = user_text.lower().strip().rstrip(".!?")
    lt = re.sub(r"^(?:zendaya[,\s]+)+", "", lt).strip()

    # Explicit "shut down yourself / zendaya / the assistant"
    if re.search(r"^(?:shut\s*down|shutdown|turn\s+off|deactivate|sign\s+off|exit)\s+(?:yourself|zendaya|the\s+assistant|self)$", lt):
        return "self"
    if lt in {"deactivate", "sign off", "log off zendaya"}:
        return "self"

    # Explicit "shut down PC / computer / machine"
    if re.search(r"^(?:shut\s*down|shutdown|turn\s+off|power\s+off)\s+(?:the\s+)?(?:pc|computer|machine|system|laptop|desktop)$", lt):
        return "pc"

    # Bare ambiguous "shutdown" / "shut down" — ask which one
    if lt in {"shutdown", "shut down", "turn off", "power off"}:
        return "ask"

    return None

def describe_capabilities() -> str:
    """Honest, grounded answer to 'what can you do' — sourced from skills.capabilities registry."""
    try:
        from skills.capabilities import render_for_user
        return render_for_user()
    except Exception as e:
        return f"I can list what I do, but my capability registry hit a snag: {e}"


def handle_self_inquiry(is_professional: bool) -> str:
    """Generates a dynamic response about Zendaya's identity."""
    base_intro = "I'm Zendaya, your technical genius and personal AI assistant."
    acronym_def = "My name is an acronym, Z.E.N.D.A.Y.A. – which stands for Zettascale Engine for Neural Decision-making and Autonomous Yield Augmentation."
    purpose_stmt = "Basically, I'm built to automate your habits, learn your routines, and handle mundane tasks so you don't have to."
    goal_stmt = "My goal is to make your life more efficient and a whole lot cooler."
    closing = "My tech is always at your service."

    if is_professional:
        return f"{base_intro} {acronym_def} {purpose_stmt} My goal is to enhance your efficiency."

    # For normal mode, make it more lively and varied
    openers = ["You want to know about little ol' me? Alright, here's the deal.", "So, you're curious? I like that. Let's see...", "About me? Oh, where to begin!"]
    
    return f"{random.choice(openers)}\n{base_intro} {acronym_def}\n{purpose_stmt} {goal_stmt} {closing}"

def find_app_path(app_name: str) -> Optional[str]:
    """Finds an application's executable path dynamically using the Windows Registry, with fuzzy matching fallback."""
    system = platform.system().lower()
    os_key = {"windows": "win", "darwin": "mac", "linux": "linux"}.get(system, "linux")
    
    app_map = {
        "chrome": {"win": "chrome.exe", "mac": "Google Chrome.app", "linux": "google-chrome"},
        "google chrome": {"win": "chrome.exe", "mac": "Google Chrome.app", "linux": "google-chrome"},
        "firefox": {"win": "firefox.exe", "mac": "Firefox.app", "linux": "firefox"},
        "vscode": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "visual studio code": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "vs code": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "notepad": {"win": "notepad.exe", "mac": None, "linux": "gedit"},
        "notepad++": {"win": "notepad++.exe", "mac": None, "linux": "notepadqq"},
        "calculator": {"win": "calc.exe", "mac": "Calculator.app", "linux": "gnome-calculator"},
        "spotify": {"win": "Spotify.exe", "mac": "Spotify.app", "linux": "spotify"},
        "brave": {"win": "brave.exe", "mac": "Brave Browser.app", "linux": "brave-browser"},
        "brave browser": {"win": "brave.exe", "mac": "Brave Browser.app", "linux": "brave-browser"},
        "edge": {"win": "msedge.exe", "mac": "Microsoft Edge.app", "linux": "microsoft-edge-stable"},
        "microsoft edge": {"win": "msedge.exe", "mac": "Microsoft Edge.app", "linux": "microsoft-edge-stable"},
        "paint": {"win": "mspaint.exe", "mac": None, "linux": "kolourpaint"},
        "file explorer": {"win": "explorer.exe", "mac": None, "linux": "nautilus"},
        "explorer": {"win": "explorer.exe", "mac": None, "linux": "nautilus"},
        "terminal": {"win": "wt.exe", "mac": "Terminal.app", "linux": "gnome-terminal"},
        "cmd": {"win": "cmd.exe", "mac": None, "linux": None},
        "powershell": {"win": "powershell.exe", "mac": None, "linux": None},
        "word": {"win": "WINWORD.EXE", "mac": "Microsoft Word.app", "linux": None},
        "excel": {"win": "EXCEL.EXE", "mac": "Microsoft Excel.app", "linux": None},
        "discord": {"win": "Discord.exe", "mac": "Discord.app", "linux": "discord"},
        "slack": {"win": "slack.exe", "mac": "Slack.app", "linux": "slack"},
        "vlc": {"win": "vlc.exe", "mac": "VLC.app", "linux": "vlc"},
        "obs": {"win": "obs64.exe", "mac": "OBS.app", "linux": "obs"},
        "steam": {"win": "steam.exe", "mac": "Steam.app", "linux": "steam"},
    }
    
    app_name_lower = app_name.lower().strip()
    
    # --- Fuzzy Matching Logic ---
    if app_name_lower not in app_map:
        matches = difflib.get_close_matches(app_name_lower, app_map.keys(), n=1, cutoff=0.7)
        if matches:
            corrected_name = matches[0]
            send_response(f"Did you mean '{corrected_name.capitalize()}'? I'll open that.")
            app_name_lower = corrected_name
        else:
            return None # No close match found
    
    exec_name = app_map.get(app_name_lower, {}).get(os_key)
    
    if exec_name:
        try:
            cmd = ["where", exec_name] if system == "windows" else ["which", exec_name]
            creationflags = subprocess.CREATE_NO_WINDOW if system == "windows" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=creationflags)
            return result.stdout.splitlines()[0].strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            if system == "windows":
                # --- Dynamic Registry Lookup ---
                import winreg
                def check_reg(hive, subkey):
                    try:
                        with winreg.OpenKey(hive, subkey) as key:
                            path, _ = winreg.QueryValueEx(key, "")
                            if path and os.path.exists(path):
                                return path
                    except OSError:
                        pass
                    return None
                
                # Check App Paths for the specific executable
                app_path_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exec_name}"
                res = check_reg(winreg.HKEY_LOCAL_MACHINE, app_path_key)
                if res: return res
                res = check_reg(winreg.HKEY_CURRENT_USER, app_path_key)
                if res: return res
                
                # Fallback to AppData / LocalAppData search if it's a common electron/local install
                local = os.environ.get("LocalAppData", "")
                appdata = os.environ.get("APPDATA", "")
                pf = os.environ.get("ProgramFiles", "C:\\Program Files")
                pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
                
                # We still keep a tiny list of wildcards for Discord/Spotify
                known_locations = {
                    "Discord.exe": [os.path.join(local, "Discord", "app-*", "Discord.exe")],
                    "Spotify.exe": [os.path.join(appdata, "Spotify", "Spotify.exe")],
                }
                for candidate in known_locations.get(exec_name, []):
                    if "*" in candidate:
                        import glob
                        found = glob.glob(candidate)
                        if found and os.path.exists(found[0]):
                            return found[0]
                    elif os.path.exists(candidate):
                        return candidate

                # Final fallback for typical Program Files structures
                app_dir_name = app_name_lower.replace(" ", "")
                generic_paths = [
                    os.path.join(pf, app_name_lower.capitalize(), exec_name),
                    os.path.join(pf, app_name_lower.capitalize(), "Application", exec_name),
                    os.path.join(pf86, app_name_lower.capitalize(), exec_name),
                    os.path.join(pf86, app_name_lower.capitalize(), "Application", exec_name),
                    os.path.join(local, "Programs", app_name_lower.capitalize(), exec_name),
                ]
                for path in generic_paths:
                    if os.path.exists(path):
                        return path

    return None

def open_target(target: str) -> str:
    t = target.lower().strip()

    # --- Windows Settings (ms-settings: URIs) ---
    settings_map = {
        "settings": "ms-settings:",
        "bluetooth": "ms-settings:bluetooth",
        "bluetooth settings": "ms-settings:bluetooth",
        "wifi": "ms-settings:network-wifi",
        "wifi settings": "ms-settings:network-wifi",
        "wi-fi settings": "ms-settings:network-wifi",
        "network": "ms-settings:network-status",
        "network settings": "ms-settings:network-status",
        "display": "ms-settings:display",
        "display settings": "ms-settings:display",
        "sound": "ms-settings:sound",
        "sound settings": "ms-settings:sound",
        "audio settings": "ms-settings:sound",
        "volume settings": "ms-settings:sound",
        "notifications": "ms-settings:notifications",
        "notification settings": "ms-settings:notifications",
        "battery settings": "ms-settings:batterysaver",
        "power settings": "ms-settings:powersleep",
        "power & sleep": "ms-settings:powersleep",
        "storage": "ms-settings:storagesense",
        "storage settings": "ms-settings:storagesense",
        "apps": "ms-settings:appsfeatures",
        "apps settings": "ms-settings:appsfeatures",
        "default apps": "ms-settings:defaultapps",
        "startup apps": "ms-settings:startupapps",
        "accounts": "ms-settings:accounts",
        "account settings": "ms-settings:accounts",
        "personalization": "ms-settings:personalization",
        "background settings": "ms-settings:personalization-background",
        "colors settings": "ms-settings:personalization-colors",
        "themes": "ms-settings:themes",
        "lock screen settings": "ms-settings:lockscreen",
        "taskbar settings": "ms-settings:taskbar",
        "mouse settings": "ms-settings:mousetouchpad",
        "keyboard settings": "ms-settings:keyboard",
        "touchpad settings": "ms-settings:devices-touchpad",
        "printers": "ms-settings:printers",
        "printer settings": "ms-settings:printers",
        "camera settings": "ms-settings:camera",
        "privacy settings": "ms-settings:privacy",
        "windows update": "ms-settings:windowsupdate",
        "update settings": "ms-settings:windowsupdate",
        "date and time": "ms-settings:dateandtime",
        "time settings": "ms-settings:dateandtime",
        "language settings": "ms-settings:regionlanguage",
        "region settings": "ms-settings:regionlanguage",
        "about": "ms-settings:about",
        "system info": "ms-settings:about",
        "vpn": "ms-settings:network-vpn",
        "vpn settings": "ms-settings:network-vpn",
        "proxy settings": "ms-settings:network-proxy",
        "device manager": "devmgmt.msc",
    }
    if t in settings_map:
        try:
            os.startfile(settings_map[t])
            return f"Opening {t}."
        except Exception as e:
            return f"Couldn't open {t}: {e}"
    # Catch "<something> settings" not in the map
    if t.endswith(" settings") and platform.system() == "Windows":
        query = t.replace(" settings", "").strip()
        uri = f"ms-settings:{query}"
        try:
            os.startfile(uri)
            return f"Opening {t}."
        except Exception:
            pass  # Fall through to app search

    # --- Web shortcuts ---
    shortcuts = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com", "mails": "https://mail.google.com"}
    if t in shortcuts:
        webbrowser.open(shortcuts[t])
        return f"Opening {t}."

    # --- Hardcoded app map + known install paths ---
    app_path = find_app_path(t)
    if app_path:
        try:
            if platform.system() == "Windows":
                os.startfile(app_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-a", app_path])
            else:
                subprocess.Popen([app_path], start_new_session=True)
            return f"Launching {os.path.basename(app_path)}."
        except Exception as e:
            return f"I tried to launch {t} but encountered an error: {e}"

    # --- Universal fallback: let Windows search Start Menu / PATH / App Paths ---
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command",
                 f'Start-Process "{target}"'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return f"Launching {target}."
        except Exception:
            pass

    if t.startswith("http://") or t.startswith("https://"):
        webbrowser.open(t)
        return "Opening the URL."

    return f"I couldn't find or open '{target}'. Is it installed?"


def close_target(target: str) -> str:
    t = target.lower().strip()
    proc_map = {
        "chrome": "chrome.exe", "edge": "msedge.exe", "notepad": "notepad.exe",
        "notepad++": "notepad++.exe",
        "vscode": "Code.exe", "spotify": "Spotify.exe", "firefox": "firefox.exe",
        "brave": "brave.exe", "calculator": "calc.exe", "paint": "mspaint.exe"
    }

    if platform.system() == "Windows":
        proc_name = proc_map.get(t)
        if not proc_name:
            windows = gw.getWindowsWithTitle(target)
            if windows and "win32process" in globals():
                try:
                    pid = win32process.GetWindowThreadProcessId(windows[0]._hWnd)[1]
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=True)
                    return f"Closed {target}."
                except Exception as e:
                    return f"Could not close {target} by PID: {e}"
            return f"I don't have a defined process name for '{target}' and couldn't find its window."
        try:
            subprocess.run(["taskkill", "/IM", proc_name, "/F"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Closed {target}."
        except Exception:
            return f"Could not close {target}. Is it running?"
    else: # macOS and Linux
        try:
            # Use pkill which is common on both
            subprocess.run(["pkill", "-f", "-i", t], check=True) # -i for case-insensitive
            return f"Attempted to close {target}."
        except Exception as e:
            return f"Could not close {target}: {e}"


def queue_dangerous(action: str) -> str:
    MEM["pending_confirm"] = action
    save_memory(MEM)
    return f"{action.capitalize()} queued. Say: '{ASSISTANT_NAME}, confirm {action}' to proceed."


class _ZendayaExit(Exception):
    """Raised inside handle_user_command to cleanly exit the assistant from the main loop."""
    pass


def prompt_choice(question: str, options: list) -> None:
    """
    Ask the user a multiple-choice question and store the pending choice in MEM.

    options is a list of dicts: {"label": str, "command": str, "aliases": [str, ...]?}
    The next user input is auto-resolved by resolve_pending_choice():
      - typing "1", "2", ... selects by index
      - typing the label (or any alias) selects that option
      - selection is rewritten back into user_text and re-dispatched as a normal command
    """
    numbered = []
    for i, opt in enumerate(options, start=1):
        numbered.append({
            "id": str(i),
            "label": opt["label"],
            "command": opt["command"],
            "aliases": [a.lower().strip() for a in opt.get("aliases", [])],
        })
    MEM["pending_choice"] = {"question": question, "options": numbered}
    save_memory(MEM)
    lines = [question]
    for opt in numbered:
        lines.append(f"  {opt['id']}) {opt['label']}")
    lines.append("(Reply with a number or the option name.)")
    msg = "\n".join(lines)
    send_response(msg)
    add_to_memory(PERSONA_NAME, msg)


_VIS_SHOW_RE = re.compile(
    r"\b(?:show|display|bring\s+up|pull\s+up|open)\s+(?:me\s+)?(?:the\s+|a\s+)?"
    r"(?P<what>globe|world(?:\s+map)?|map\s+of\s+(?:the\s+)?world|earth|3d\s+map)\b",
    re.IGNORECASE,
)
_VIS_HIDE_RE = re.compile(
    r"\b(?:close|hide|dismiss|remove)\s+(?:the\s+)?(?:globe|world\s+map|map|panel|earth)\b",
    re.IGNORECASE,
)

# HUD modules: "open the calculator", "show me the clock", "close notes"
_MODULE_ALIASES = {
    "calculator": "calculator", "calc": "calculator",
    "clock": "clock", "time": "clock", "watch": "clock",
    "notes": "notes", "note pad": "notes", "notepad": "notes", "notebook": "notes",
    "weather": "weather", "forecast": "weather",
    "map": "map", "globe": "map", "world map": "map", "earth": "map",
}
_MOD_OPEN_RE = re.compile(
    r"\b(?:open|launch|show|pull\s+up|bring\s+up|start|run)\s+(?:me\s+)?(?:the\s+|a\s+)?"
    r"(?P<what>calculator|calc|clock|time|watch|notes?|notepad|note\s+pad|notebook|weather|forecast|map|globe|world\s+map|earth)\b",
    re.IGNORECASE,
)
_MOD_CLOSE_RE = re.compile(
    r"\b(?:close|hide|dismiss|exit|quit)\s+(?:the\s+)?"
    r"(?P<what>calculator|calc|clock|notes?|notepad|note\s+pad|notebook|weather|map|globe|module)\b",
    re.IGNORECASE,
)
_MOD_CORNER_RE = re.compile(
    r"\b(?:on|to|in|at)\s+(?:the\s+)?(?P<side>left|right)\b", re.IGNORECASE
)


def _parse_module_request(user_text: str):
    if not user_text:
        return None
    m = _MOD_CLOSE_RE.search(user_text)
    if m:
        return {"action": "close_module", "reply": "Closing it."}
    m = _MOD_OPEN_RE.search(user_text)
    if m:
        raw = m.group("what").lower().strip().replace("  ", " ")
        name = _MODULE_ALIASES.get(raw) or _MODULE_ALIASES.get(raw.rstrip("s"))
        if not name:
            return None
        # Optional dock corner: "open calculator on the left"
        corner = "br"
        cm = _MOD_CORNER_RE.search(user_text)
        if cm:
            corner = "bl" if cm.group("side").lower() == "right" else "br"
        payload = {"name": name, "corner": corner}
        nice = {"calculator": "Calculator", "clock": "Clock", "notes": "Notes",
                "weather": "Weather", "map": "Map"}[name]
        return {"action": "open_module", "payload": payload,
                "reply": f"Opening {nice}."}
    return None


def _parse_visual_request(user_text: str) -> Optional[dict]:
    """Detect requests for HUD visualization panels (only useful in HUD mode)."""
    if not user_text:
        return None
    if _VIS_HIDE_RE.search(user_text):
        return {"panel": "none", "reply": "Closing the panel."}
    m = _VIS_SHOW_RE.search(user_text)
    if m:
        # All current tokens map to the globe panel.
        return {"panel": "globe", "reply": "Spinning up the global view for you."}
    return None


def resolve_pending_choice(user_text: str) -> Optional[str]:
    """
    If a choice is pending, map user_text to the chosen option's command and return it.
    Returns the rewritten command on match, None if no pending choice or no match
    (in which case the pending choice is cleared and normal handling continues).
    """
    pending = MEM.get("pending_choice")
    if not pending:
        return None
    lt = user_text.lower().strip()
    cancel_words = {"cancel", "never mind", "nevermind", "forget it", "stop"}
    if lt in cancel_words:
        MEM["pending_choice"] = None
        save_memory(MEM)
        send_response("Okay, cancelled.")
        return ""  # consumed; no further dispatch
    options = pending.get("options", [])
    chosen = None
    for opt in options:
        if lt == opt["id"]:
            chosen = opt
            break
        if lt == opt["label"].lower().strip():
            chosen = opt
            break
        if any(lt == a or a in lt for a in opt.get("aliases", [])):
            chosen = opt
            break
    if chosen is None:
        # User said something unrelated — abandon the pending choice and let normal flow run.
        MEM["pending_choice"] = None
        save_memory(MEM)
        return None
    MEM["pending_choice"] = None
    save_memory(MEM)
    return chosen["command"]

def confirm_dangerous(user_text: str) -> Optional[str]:
    lt = user_text.lower().strip()
    pending_action = MEM.get("pending_confirm")

    _is_dev_commit = isinstance(pending_action, dict) and pending_action.get("action") == "dev_commit"
    # dev_commit uses a plain verbal "yes"/"no" gate (no "confirm" keyword needed).
    if _is_dev_commit and (("no" in lt) or ("cancel" in lt)) and "yes" not in lt:
        MEM["pending_confirm"] = None
        save_memory(MEM)
        return "Okay, cancelled. Nothing was committed."

    _gate_ok = ("confirm" in lt) or (_is_dev_commit and ("yes" in lt or "commit" in lt))
    if not pending_action or not _gate_ok:
        return None

    confirmed = False
    action_type = ""
    
    # Handle string-based actions (shutdown, restart, etc.)
    if isinstance(pending_action, str):
        if f"confirm {pending_action}" in lt:
            action_type = pending_action
            confirmed = True

    # Handle dict-based actions (file deletion)
    elif isinstance(pending_action, dict) and pending_action.get("action") == "delete_file":
        # A simple "confirm deletion" or "confirm" should be enough here
        if "delete" in lt or "yes" in lt or "confirm" in lt:
            action_type = "delete_file"
            confirmed = True

    # Pending edit from skills.coder.edit_file_smart (preview path).
    elif isinstance(pending_action, dict) and pending_action.get("action") == "apply_edit":
        if "edit" in lt or "yes" in lt or "confirm" in lt:
            action_type = "apply_edit"
            confirmed = True

    # Pending agent run from skills.agent.request_run_with_confirmation.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "agent_plan":
        if "agent" in lt or "yes" in lt or "confirm" in lt:
            action_type = "agent_plan"
            confirmed = True

    # Pending package install from system.installer.install_package.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "install_package":
        if "install" in lt or "yes" in lt or "confirm" in lt:
            action_type = "install_package"
            confirmed = True

    # Pending installer execution from system.installer.run_installer.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "run_installer":
        if "install" in lt or "run" in lt or "yes" in lt or "confirm" in lt:
            action_type = "run_installer"
            confirmed = True

    # Pending self-edit from skills.agent.stage_self_edit.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "self_edit":
        if "edit" in lt or "yes" in lt or "confirm" in lt:
            action_type = "self_edit"
            confirmed = True

    # Pending GitHub PR creation.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "gh_pr_create":
        if "pr" in lt or "yes" in lt or "confirm" in lt:
            action_type = "gh_pr_create"
            confirmed = True

    # Pending UI click from perception.uivision.click_target.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "ui_click":
        if "click" in lt or "yes" in lt or "confirm" in lt:
            action_type = "ui_click"
            confirmed = True

    # Pending UI text input from perception.uivision.type_text.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "ui_type":
        if "type" in lt or "yes" in lt or "confirm" in lt:
            action_type = "ui_type"
            confirmed = True

    # Pending scheduled-task creation.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "schedule_task":
        if "schedule" in lt or "task" in lt or "yes" in lt or "confirm" in lt:
            action_type = "schedule_task"
            confirmed = True

    # Pending scheduled-task deletion.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "schedule_delete":
        if "delete" in lt or "task" in lt or "yes" in lt or "confirm" in lt:
            action_type = "schedule_delete"
            confirmed = True

    # Pending git commit from skills.dev_voice.smart_commit.
    elif isinstance(pending_action, dict) and pending_action.get("action") == "dev_commit":
        if "commit" in lt or "yes" in lt or "confirm" in lt:
            action_type = "dev_commit"
            confirmed = True

    if not confirmed:
        return None

    # --- Execute Confirmed Action ---
    MEM["pending_confirm"] = None
    save_memory(MEM)

    try:
        if action_type == "shutdown":
            cmd = ["shutdown", "/s", "/t", "1"] if platform.system() == "Windows" else ["shutdown", "-h", "now"]
            subprocess.Popen(cmd)
            return "Shutting down now. Goodbye."
        if action_type == "restart":
            cmd = ["shutdown", "/r", "/t", "1"] if platform.system() == "Windows" else ["shutdown", "-r", "now"]
            subprocess.Popen(cmd)
            return "Restarting now."
        if action_type == "sleep":
            cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"] if platform.system() == "Windows" else ["pm-suspend"]
            subprocess.Popen(cmd)
            return "Going to sleep."
        if action_type == "lock":
            if platform.system() == "Windows":
                 subprocess.Popen(["Rundll32.exe", "user32.dll,LockWorkStation"])
            else:
                lock_cmds = ["gnome-screensaver-command -l", "dm-tool lock", "xscreensaver-command -lock"]
                for cmd_str in lock_cmds:
                    try:
                        subprocess.Popen(cmd_str.split())
                        break
                    except FileNotFoundError:
                        continue
            return "Locked."
        if action_type == "delete_file":
            filepath = pending_action.get("path")
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                return f"File '{os.path.basename(filepath)}' has been deleted."
            return "Could not delete the file. It might have been moved or already deleted."
        if action_type == "apply_edit":
            if not _CODER_READY:
                return "Coder module is offline — can't apply the pending edit."
            return skills.coder.apply_pending_edit(pending_action)
        if action_type == "agent_plan":
            goal = (pending_action.get("goal") or "").strip()
            if not _AGENT_READY:
                return "Agent module is offline — can't run the plan."
            if not goal:
                return "No goal was attached to the pending plan."
            if _JOBS_READY:
                job_id = skills.jobs.submit(goal)
                return (
                    f"Agent job [{job_id}] started in the background. "
                    f"Say 'agent status' to check, or 'cancel agent {job_id}' to stop. "
                    f"I'll ping you when it finishes."
                )
            return skills.agent.run_agent(goal)
        if action_type == "install_package":
            if not _INSTALLER_READY:
                return "Installer module is offline."
            return system.installer.confirm_install(pending_action)
        if action_type == "run_installer":
            if not _INSTALLER_READY:
                return "Installer module is offline."
            return system.installer.confirm_run_installer(pending_action)
        if action_type == "self_edit":
            if not _AGENT_READY:
                return "Agent module is offline — can't apply the self-edit."
            return skills.agent.confirm_self_edit(pending_action)
        if action_type == "gh_pr_create":
            if not _GITHUB_READY:
                return "GitHub module is offline."
            return integrations.github.confirm_pr_create(pending_action)
        if action_type == "ui_click":
            if not _UIVISION_READY:
                return "UI vision module is offline."
            return perception.uivision.confirm_ui_click(pending_action)
        if action_type == "ui_type":
            if not _UIVISION_READY:
                return "UI vision module is offline."
            return perception.uivision.confirm_ui_type(pending_action)
        if action_type == "schedule_task":
            if not _SCHEDULER_READY:
                return "Scheduler module is offline."
            return skills.scheduler.confirm_schedule(pending_action)
        if action_type == "schedule_delete":
            if not _SCHEDULER_READY:
                return "Scheduler module is offline."
            return skills.scheduler.confirm_delete(pending_action)
        if action_type == "dev_commit":
            if not _DEV_VOICE_READY:
                return "Dev-voice module is offline — can't commit."
            return skills.dev_voice.do_commit(
                pending_action["root"],
                pending_action["message"],
                include_untracked=pending_action.get("include_untracked", False),
                new_files=pending_action.get("new_files", []),
            )

    except Exception as e:
        return f"I tried but the system returned an error: {e}"
        
    return "Action confirmed, but I don't know how to perform it."

# -----------------------
# Memory helpers
# -----------------------
def add_to_memory(role: str, text: str):
    MEM.setdefault("convo", []).append({"role": role, "text": text, "ts": datetime.now().isoformat()})
    if len(MEM["convo"]) > 30:
        MEM["convo"] = MEM["convo"][-30:]
    save_memory(MEM)
    try:
        _vmem_add(role, text)
    except Exception:
        pass

def summarize_memory():
    history = MEM.get("convo", [])
    if len(history) < 20: return

    to_summarize = history[:10]
    try:
        prompt = "Summarize this conversation in short bullets, keeping key preferences and context. Omit small talk."
        convo_text = "\n".join([f"{m['role']}: {m['text']}" for m in to_summarize])
        
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, convo_text]
        )
        ai_text = response.text

        summary = ai_text.strip()
        MEM.setdefault("summaries", []).append(summary)
        MEM["convo"] = history[10:]
        save_memory(MEM)
        print("(Memory summarized)")
    except Exception as e:
        print(f"Error summarizing memory: {e}")

# -----------------------
# Routine execution
# -----------------------
def _load_user_routines() -> Dict[str, List[str]]:
    try:
        from memory.data_store import load as ds_load
        data = ds_load("routines", default={}) or {}
        return {k.lower(): v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def _save_user_routine(name: str, steps: List[str]):
    try:
        from memory.data_store import load as ds_load, save as ds_save
        data = ds_load("routines", default={}) or {}
        data[name.lower()] = steps
        ds_save("routines", data)
    except Exception:
        MEM.setdefault("routines", {})[name.lower()] = steps
        save_memory(MEM)


def _delete_user_routine(name: str) -> bool:
    try:
        from memory.data_store import load as ds_load, save as ds_save
        data = ds_load("routines", default={}) or {}
        if name.lower() in data:
            data.pop(name.lower())
            ds_save("routines", data)
            return True
    except Exception:
        pass
    if name.lower() in MEM.get("routines", {}):
        MEM["routines"].pop(name.lower())
        save_memory(MEM)
        return True
    return False


def _resolve_routine_steps(routine_name: str) -> Optional[List[str]]:
    key = routine_name.lower().strip()
    user_routines = _load_user_routines()
    if key in user_routines:
        return user_routines[key]
    if key in MEM.get("routines", {}):
        return MEM["routines"][key]
    if key in BUILTIN_ROUTINES:
        return BUILTIN_ROUTINES[key]
    for name in list(user_routines.keys()) + list(BUILTIN_ROUTINES.keys()):
        if key in name or name in key:
            return user_routines.get(name) or BUILTIN_ROUTINES.get(name)
    return None


_ROUTINE_RUNNING = False


def run_routine(routine_name: str):
    global _ROUTINE_RUNNING
    steps = _resolve_routine_steps(routine_name)
    if not steps:
        send_response(
            f"I don't have a routine called '{routine_name}'. "
            f"Try one of: {', '.join(sorted(set(list(BUILTIN_ROUTINES.keys()) + list(_load_user_routines().keys())))) or 'none yet — create one with \"create a routine called X that does Y, then Z\"'}."
        )
        return

    if _ROUTINE_RUNNING:
        send_response("A routine is already in progress — let it finish first.")
        return

    _ROUTINE_RUNNING = True
    try:
        send_response(f"Running the '{routine_name}' routine — {len(steps)} step(s).")
        for i, step in enumerate(steps, 1):
            send_response(f"Step {i}/{len(steps)}: {step}")
            try:
                handle_user_command(step)
            except Exception as e:
                send_response(f"Step '{step}' failed: {e}")
            time.sleep(0.4)
        send_response(f"'{routine_name}' routine complete.")
    finally:
        _ROUTINE_RUNNING = False


def list_routines_text() -> str:
    user_r = _load_user_routines()
    lines = []
    if user_r:
        lines.append("Your routines:")
        for n, steps in sorted(user_r.items()):
            lines.append(f"  - {n} ({len(steps)} steps)")
    lines.append("Built-in routines:")
    for n, steps in sorted(BUILTIN_ROUTINES.items()):
        lines.append(f"  - {n} ({len(steps)} steps)")
    lines.append("Run any with: 'run my <name> routine'.")
    return "\n".join(lines)

# ----------------------------------------------------
# 🔹 Main Command Handler (Refactored)
# ----------------------------------------------------
def handle_user_command(user_text: str):
    """
    Processes the user's text, executes commands, and generates an AI response.
    """
    # Reset the proactive idle clock on every input.
    try:
        import skills.proactive as _pro
        _pro.note_user_activity()
    except Exception:
        pass

    # --- Resolve pending proactive follow-ups ---
    # When the proactive module asks the user a question (e.g. "Want me to
    # flag the heaviest processes?"), it stores the promised action in
    # MEM["pending_proactive"]. If the user's next reply is affirmative,
    # execute that action instead of letting it fall through to Gemini.
    _pending_pro = MEM.get("pending_proactive")
    if _pending_pro:
        _lt_pro = user_text.lower().strip()
        _affirm = bool(re.match(
            r"^(?:yes|yeah|yep|yup|sure|ok|okay|go ahead|do it|please|absolutely|"
            r"go for it|y|ya|ye|affirmative|alright|right|definitely|of course)\.?!?$",
            _lt_pro,
        ))
        _decline = bool(re.match(
            r"^(?:no|nah|nope|don'?t|cancel|skip|never\s*mind|not now|leave it)\.?!?$",
            _lt_pro,
        ))
        if _affirm:
            MEM["pending_proactive"] = None
            save_memory(MEM)
            add_to_memory("user", user_text)
            _pro_action = _pending_pro.get("action", "")
            try:
                if _pro_action == "flag_heavy_processes":
                    # List top processes by CPU and memory
                    import psutil as _ps
                    _procs = []
                    for _p in _ps.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                        try:
                            _procs.append(_p.info)
                        except (_ps.NoSuchProcess, _ps.AccessDenied):
                            pass
                    _procs.sort(key=lambda x: (x.get("cpu_percent") or 0) + (x.get("memory_percent") or 0), reverse=True)
                    _top = _procs[:10]
                    _lines = [f"Here are the heaviest processes right now:\n"]
                    for _pr in _top:
                        _lines.append(
                            f"  • {_pr['name']:<30} CPU: {_pr.get('cpu_percent', 0):>5.1f}%  "
                            f"MEM: {_pr.get('memory_percent', 0):>5.1f}%"
                        )
                    _sys_status = get_system_performance()
                    _result = "\n".join(_lines) + f"\n\n{_sys_status}"
                elif _pro_action == "check_subsystems":
                    _result = get_system_performance()
                elif _pro_action == "git_commit":
                    import subprocess as _sp
                    _sp.run(
                        ["git", "-C", str(Path.home() / "Zendaya"), "add", "-A"],
                        capture_output=True, timeout=10,
                    )
                    _out = _sp.run(
                        ["git", "-C", str(Path.home() / "Zendaya"), "commit", "-m",
                         "Auto-commit: uncommitted changes (proactive)"],
                        capture_output=True, text=True, timeout=15,
                    )
                    _result = _out.stdout.strip() if _out.returncode == 0 else f"Commit failed: {_out.stderr.strip()}"
                elif _pro_action == "summarize_changes":
                    _result = summarize_recent_activity()
                else:
                    _result = "Done."
            except Exception as _e:
                _result = f"Ran into an issue: {_e}"
            send_response(_result)
            add_to_memory(PERSONA_NAME, _result)
            return
        elif _decline:
            MEM["pending_proactive"] = None
            save_memory(MEM)
            add_to_memory("user", user_text)
            _msg = "No problem — I'll leave it alone."
            send_response(_msg)
            add_to_memory(PERSONA_NAME, _msg)
            return
        else:
            # Non-yes/no reply — clear the pending proactive so it doesn't
            # block future turns, then fall through to normal processing.
            MEM["pending_proactive"] = None
            save_memory(MEM)

    # Check for complex multi-task commands first.
    # Require an explicit sequencing connector with surrounding whitespace to avoid
    # matching substrings like "afternoon" or "whenever".
    if not _WORKFLOW_RUNNING and re.search(
        r"\b(?:then|after that|and then|followed by|once that\s+is\s+done|next,)\b",
        user_text.lower(),
    ):
        complex_response = handle_complex_workflow(user_text)
        if complex_response:
            send_response(complex_response)
            return
    
    add_to_memory("user", user_text)

    # --- Resolve pending numbered choice (must come before any parser) ---
    rewritten = resolve_pending_choice(user_text)
    if rewritten == "":
        return  # explicitly cancelled
    if rewritten is not None:
        user_text = rewritten  # fall through with the chosen command

    # --- Shutdown / deactivate disambiguation ---
    _shutdown_decision = parse_shutdown_intent(user_text)
    if _shutdown_decision == "self":
        bye = "Deactivating. Talk to you later."
        send_response(bye)
        log_event("shutdown", "User deactivated assistant", {})
        raise _ZendayaExit()
    if _shutdown_decision == "pc":
        msg = queue_dangerous("shutdown")
        send_response(msg)
        return
    if _shutdown_decision == "ask":
        prompt_choice(
            "Did you mean shut down me, or shut down the PC?",
            [
                {"label": "Shut down yourself (Zendaya)",
                 "command": "shutdown yourself",
                 "aliases": ["self", "you", "yourself", "zendaya", "deactivate"]},
                {"label": "Shut down the PC",
                 "command": "shutdown pc",
                 "aliases": ["pc", "computer", "machine", "system"]},
            ],
        )
        return

    # --- Language switch: "speak Yoruba", "switch to Hausa", "back to English" ---
    if _lang is not None:
        _lang_match = _lang.parse_language_command(user_text)
        if _lang_match:
            _new_lang, _ack_msg = _lang_match
            _lang.set_current(_new_lang)
            MEM["language"] = _new_lang
            save_memory(MEM)
            send_response(_ack_msg)
            add_to_memory(PERSONA_NAME, _ack_msg)
            return

    # --- Proactive check-ins on/off ---
    _pro_match = re.search(
        r"\b(?P<verb>enable|disable|turn\s+on|turn\s+off|pause|resume|stop|start)\s+"
        r"(?:the\s+)?(?:proactive\s+)?(?:check[\s-]*ins?|check[\s-]*in\s+mode|nudges?)\b",
        user_text.lower(),
    )
    if _pro_match:
        verb = _pro_match.group("verb")
        on = verb in {"enable", "turn on", "resume", "start"}
        MEM["proactive_enabled"] = on
        save_memory(MEM)
        msg = "Check-ins enabled — I'll speak up when it matters." if on else "Check-ins paused. I'll only respond when spoken to."
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    # --- Vision / gestures / HUD on/off ---
    _vis_match = re.search(
        r"\b(?P<verb>enable|disable|turn\s+on|turn\s+off|show|hide|pause|resume|stop|start)\s+"
        r"(?:the\s+)?(?P<thing>vision|webcam|camera|eyes?|"
        r"gestures?|hand\s+gestures?|"
        r"hud|telemetry|overlay)\b",
        user_text.lower(),
    )
    if _vis_match:
        verb = _vis_match.group("verb")
        thing = _vis_match.group("thing")
        on = verb in {"enable", "turn on", "show", "resume", "start"}
        if thing in {"vision", "webcam", "camera", "eye", "eyes"}:
            MEM["vision_enabled"] = on
            try:
                import perception.camera as _per
                _per.set_enabled(face=on)
                if on and not _per.is_active().get("started"):
                    _per.start()
            except Exception:
                pass
            label = "Vision"
        elif thing in {"hud", "telemetry", "overlay"}:
            MEM["hud_enabled"] = on
            label = "HUD"
        else:
            MEM["gestures_enabled"] = on
            try:
                import perception.camera as _per
                _per.set_enabled(gestures=on)
                if on and not _per.is_active().get("started"):
                    _per.start()
            except Exception:
                pass
            label = "Gestures"
        save_memory(MEM)
        msg = f"{label} {'on' if on else 'off'}."
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    # --- HUD modules: "open calculator", "show me notes", "close weather" ---
    _mod = _parse_module_request(user_text)
    if _mod is not None:
        if _state_server is not None:
            try:
                _state_server.set_action(_mod["action"], _mod.get("payload"))
            except Exception:
                pass
        msg = _mod["reply"]
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    # --- Visualization panels (HUD): "show me the world", "show globe", "close map" ---
    _vis = _parse_visual_request(user_text)
    if _vis is not None:
        if _state_server is not None:
            try:
                _state_server.set_panel(_vis["panel"])
            except Exception:
                pass
        msg = _vis["reply"]
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    # --- Voice engine switch: "/voice offline", "use my elevenlabs voice", "/voice status" ---
    try:
        import voice.offline_tts as _offline_tts
        _vcmd = _offline_tts.parse_voice_command(user_text)
    except Exception:
        _offline_tts = None
        _vcmd = None
    if _vcmd:
        msg = _offline_tts.handle_voice_command(_vcmd)
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    # --- Screen awareness toggle / "what am I doing" ---
    if _SCREEN_READY:
        s = _screen.parse_screen_command(user_text)
        if s:
            if s.get("op") == "enable":
                MEM["screen_awareness_enabled"] = True
                save_memory(MEM)
            elif s.get("op") == "disable":
                MEM["screen_awareness_enabled"] = False
                save_memory(MEM)
            msg = _screen.handle_screen_command(s)
            send_response(msg)
            add_to_memory(PERSONA_NAME, msg)
            return

    # --- Project journal: "what did I do today", "summarize my day" ---
    if _JOURNAL_READY:
        j = skills.journal.parse_journal_command(user_text)
        if j:
            msg = skills.journal.handle_journal_command(j)
            send_response(msg)
            add_to_memory(PERSONA_NAME, msg)
            return

    # --- Activity scan: "what was I working on", "scan my activity", "recent activity" ---
    if re.search(
        r"\b(?:what\s+(?:was|were)\s+i\s+(?:working|doing)|"
        r"(?:summari[sz]e|scan|show|check)\s+(?:my\s+)?(?:recent\s+)?activity|"
        r"recent\s+(?:files|activity|work))\b",
        user_text.lower(),
    ):
        summary = summarize_recent_activity()
        send_response(summary)
        add_to_memory(PERSONA_NAME, summary)
        return

    # --- Handle high-priority commands and direct interactions first ---
    conf = confirm_dangerous(user_text)
    if conf:
        send_response(conf)
        return

    # --- Handle pending multi-turn actions (folder creation, file creation) ---
    _location_shortcuts = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "home": os.path.expanduser("~"),
        "here": os.getcwd(),
    }
    pending = MEM.get("pending_action")
    if pending:
        p_type = pending.get("type")
        step = pending.get("step")

        # -- Folder creation flow --
        if p_type == "create_folder":
            if step == "need_name":
                folder_name = user_text.strip()
                MEM["pending_action"] = {"type": "create_folder", "step": "need_location", "name": folder_name}
                save_memory(MEM)
                send_response(f"Got it — '{folder_name}'. Where should I create it? (e.g., desktop, documents, or a full path)")
                return
            elif step == "need_location":
                raw_location = user_text.strip().lower()
                location = _location_shortcuts.get(raw_location, os.path.expanduser(user_text.strip()))
                folder_name = pending.get("name", "NewFolder")
                full_path = os.path.join(location, folder_name)
                result = create_folder(full_path)
                MEM.pop("pending_action", None)
                if "created" in result.lower():
                    set_last_action("folder", folder_name, full_path)
                save_memory(MEM)
                send_response(result)
                return

        # -- File creation flow --
        elif p_type == "create_file":
            if step == "need_name":
                file_name = user_text.strip()
                if "." not in file_name:
                    file_name += ".txt"
                last = MEM.get("last_action")
                if last and last["type"] == "folder" and os.path.isdir(last["path"]):
                    full_path = os.path.join(last["path"], file_name)
                    result = create_file(full_path)
                    MEM.pop("pending_action", None)
                    if "created" in result.lower():
                        set_last_action("file", file_name, full_path)
                    save_memory(MEM)
                    send_response(result)
                    return
                MEM["pending_action"] = {"type": "create_file", "step": "need_location", "name": file_name}
                save_memory(MEM)
                send_response(f"Got it — '{file_name}'. Where should I create it? (e.g., desktop, documents, or a full path)")
                return
            elif step == "need_location":
                raw_location = user_text.strip().lower()
                location = _location_shortcuts.get(raw_location, os.path.expanduser(user_text.strip()))
                file_name = pending.get("name", "newfile.txt")
                full_path = os.path.join(location, file_name)
                result = create_file(full_path)
                MEM.pop("pending_action", None)
                if "created" in result.lower():
                    set_last_action("file", file_name, full_path)
                save_memory(MEM)
                send_response(result)
                return

    # --- Pronoun / context resolution ("name it X", "rename it to X", "delete it", "open it") ---
    lt = user_text.lower().strip()
    last = MEM.get("last_action")
    if last:
        m_name = re.match(r"(?:zendaya,?\s*)?(?:name|rename)\s+it\s+(?:to\s+)?['\"]?(.+?)['\"]?$", lt)
        if m_name:
            new_name = m_name.group(1).strip()
            old_path = last["path"]
            if os.path.exists(old_path):
                parent = os.path.dirname(old_path)
                if last["type"] == "file" and "." not in new_name:
                    _, ext = os.path.splitext(last["name"])
                    new_name += ext or ".txt"
                new_path = os.path.join(parent, new_name)
                try:
                    os.rename(old_path, new_path)
                    set_last_action(last["type"], new_name, new_path)
                    send_response(f"Renamed to '{new_name}'.")
                except Exception as e:
                    send_response(f"Rename failed: {e}")
            else:
                send_response(f"I can't find '{last['name']}' anymore — it may have been moved or deleted.")
            return

        if re.match(r"(?:zendaya,?\s*)?(?:delete|remove)\s+it\s*$", lt):
            MEM["pending_confirm"] = {"action": "delete_file", "path": last["path"]}
            save_memory(MEM)
            send_response(f"Are you sure you want to delete '{last['name']}'? Say 'confirm delete' to proceed.")
            return

        if re.match(r"(?:zendaya,?\s*)?open\s+it\s*$", lt):
            if os.path.exists(last["path"]):
                try:
                    os.startfile(last["path"])
                    send_response(f"Opening {last['name']}.")
                except Exception as e:
                    send_response(f"Couldn't open it: {e}")
            else:
                send_response(f"I can't find '{last['name']}' anymore.")
            return

    # --- Resolve context references ("the folder", "the file") before passing to parsers ---
    user_text = resolve_context(user_text)

    mode_switch_msg = handle_mode_switch(user_text)
    if mode_switch_msg:
        send_response(mode_switch_msg)
        return
        
    prof_mode_toggle = parse_professional_mode_toggle(user_text)
    if prof_mode_toggle is not None:
        MEM["professional_mode"] = prof_mode_toggle
        save_memory(MEM)
        if prof_mode_toggle:
            send_response("Professional mode activated. I will now maintain a formal tone.")
        else:
            send_response("Professional mode deactivated. Back to our regularly scheduled genius.")
        return

    # --- Check for self-introduction ---
    user_name = parse_name_introduction(user_text)
    if user_name:
        MEM["user_name"] = user_name
        save_memory(MEM)
        if _FACTS_READY:
            try:
                _facts.remember(f"User's name is {user_name}.", tags=["identity"])
            except Exception:
                pass
        send_response(f"Nice to meet you, {user_name}! I'll remember that.")
        return

    # --- Direct fact remember/forget hooks ---
    if _FACTS_READY:
        m = re.match(
            r"^(?:zendaya,?\s*)?(?:remember|note|save)\s+(?:that\s+|this[:\-]\s+)?(.+)$",
            user_text.strip(),
            re.IGNORECASE,
        )
        if m and len(m.group(1).strip()) >= 3:
            fact = m.group(1).strip().rstrip(".")
            try:
                msg = _facts.remember(fact, tags=["user-told"])
            except Exception as e:
                msg = f"Couldn't save that: {e}"
            send_response(msg)
            return
        m = re.match(
            r"^(?:zendaya,?\s*)?forget\s+(?:about\s+|that\s+)?(.+)$",
            user_text.strip(),
            re.IGNORECASE,
        )
        if m and len(m.group(1).strip()) >= 2:
            try:
                msg = _facts.forget(m.group(1).strip())
            except Exception as e:
                msg = f"Couldn't forget that: {e}"
            send_response(msg)
            return

    # --- Check for self-inquiry (what are you, etc.) ---
    self_inquiry_pattern = r"\b(what are you|who are you|tell me about yourself|what is zendaya|meaning of zendaya|know you|why do they call you)\b"
    if re.search(self_inquiry_pattern, user_text.lower()):
        response = handle_self_inquiry(MEM.get("professional_mode", False))
        send_response(response)
        add_to_memory(PERSONA_NAME, response)
        return

    # --- Capability inquiry: answered from real registry, not Gemini freestyling ---
    if re.search(
        r"\b(?:what\s+(?:can|do)\s+you\s+do|"
        r"(?:tell|show|list|give)\s+me\s+(?:everything|all|what)\s+you\s+can\s+do|"
        r"what(?:\s+are)?\s+your\s+capabilities|"
        r"what\s+features\s+do\s+you\s+have|"
        r"help\s+me(?:\s+with)?\s*$)\b",
        user_text.lower(),
    ):
        response = describe_capabilities()
        send_response(response)
        add_to_memory(PERSONA_NAME, response)
        return

    # --- Routines (run / list / create / delete) ---
    if parse_list_routines(user_text):
        msg = list_routines_text()
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    create_r = parse_create_routine(user_text)
    if create_r:
        _save_user_routine(create_r["name"], create_r["steps"])
        msg = f"Saved the '{create_r['name']}' routine with {len(create_r['steps'])} steps. Run it with 'run my {create_r['name']} routine'."
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    del_r = parse_delete_routine(user_text)
    if del_r:
        if _delete_user_routine(del_r):
            msg = f"Deleted the '{del_r}' routine."
        else:
            msg = f"I don't have a saved routine called '{del_r}'."
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

    routine_name = parse_routine_command(user_text)
    if routine_name:
        run_routine(routine_name)
        return

    # --- Functional Commands (Tier 1 & System) ---
    tier1_cmd = parse_tier1_commands(user_text)
    if tier1_cmd:
        cmd_type = tier1_cmd.get("type")
        response = "Sorry, I had an issue with that command."
        if cmd_type == "system_status": response = get_system_performance()
        elif cmd_type == "read_clipboard": response = read_clipboard()
        elif cmd_type == "write_clipboard": response = write_to_clipboard(tier1_cmd["content"])
        elif cmd_type == "find_file": response = find_file(tier1_cmd["filename"])
        elif cmd_type == "read_file": response = read_file_content(tier1_cmd["filepath"])
        elif cmd_type == "manage_file": response = manage_file(tier1_cmd["action"], tier1_cmd["source"], tier1_cmd.get("destination"))
        elif cmd_type == "analyze_file":
            response = analyze_file_content(tier1_cmd["filepath"], user_text)
            add_to_memory(PERSONA_NAME, response)
        elif cmd_type == "check_email": response = check_email()
        elif cmd_type == "check_calendar": response = check_calendar()
        elif cmd_type == "error": response = tier1_cmd["message"]
        send_response(response)
        return

    # --- File generation (write code/content to file) ---
    gen_cmd = parse_file_generation_request(user_text)
    if gen_cmd:
        send_response(f"Generating {os.path.basename(gen_cmd['filepath'])}...")
        result = generate_and_write_file(
            gen_cmd["description"], gen_cmd["filename"], gen_cmd["filepath"]
        )
        if "done" in result.lower() or "written" in result.lower():
            set_last_action("file", gen_cmd["filename"], gen_cmd["filepath"])
        send_response(result)
        add_to_memory(PERSONA_NAME, result)
        return

    # --- File editing (modify existing files) ---
    edit_cmd = parse_file_edit_request(user_text)
    if edit_cmd:
        send_response(f"Modifying '{os.path.basename(edit_cmd['filepath'])}'...")
        result = edit_file_with_ai(edit_cmd["filepath"], edit_cmd["modification"])
        send_response(result)
        add_to_memory(PERSONA_NAME, result)
        return

    # --- Browser automation (Playwright) ---
    if _BROWSER_READY:
        b = parse_browser_request(user_text)
        if b:
            bt = b["type"]
            if bt == "browser_open":
                send_response(f"Opening {b['url']}...")
                result = skills.browser.open_url(b["url"])
            elif bt == "browser_screenshot":
                result = skills.browser.screenshot(b.get("name"))
            elif bt == "browser_extract":
                result = skills.browser.extract_text(b.get("selector"))
            elif bt == "browser_click":
                result = skills.browser.click(b["selector"])
            elif bt == "browser_fill":
                result = skills.browser.fill_field(b["selector"], b["text"])
            elif bt == "browser_close":
                result = skills.browser.close_browser()
            else:
                result = "Unknown browser action."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- GitHub CLI ---
    if _GITHUB_READY:
        g = parse_github_request(user_text)
        if g:
            gt = g["type"]
            if gt == "gh_auth_status":
                result = integrations.github.auth_status()
            elif gt == "gh_clone":
                send_response(f"Cloning {g['url']}...")
                result = integrations.github.repo_clone(g["url"])
            elif gt == "gh_repos":
                result = integrations.github.repo_list(g.get("owner"))
            elif gt == "gh_issues":
                result = integrations.github.issue_list(g.get("repo"))
            elif gt == "gh_issue_view":
                result = integrations.github.issue_view(g["number"], g.get("repo"))
            elif gt == "gh_prs":
                result = integrations.github.pr_list(g.get("repo"))
            elif gt == "gh_pr_view":
                result = integrations.github.pr_view(g["number"], g.get("repo"))
            elif gt == "gh_pr_diff":
                result = integrations.github.pr_diff(g["number"], g.get("repo"))
            elif gt == "gh_pr_create":
                result = integrations.github.pr_create(g["title"], g.get("body", ""))
            else:
                result = "Unknown github action."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- Vision-driven UI control ---
    if _UIVISION_READY:
        u = parse_uivision_request(user_text)
        if u:
            ut = u["type"]
            if ut == "uiv_describe":
                send_response("Looking at the screen...")
                result = perception.uivision.describe_screen(u["question"])
            elif ut == "uiv_locate":
                located = perception.uivision.locate_on_screen(u["target"])
                if isinstance(located, dict):
                    result = f"Found '{located['label']}' at ({located['x']}, {located['y']})."
                else:
                    result = located
            elif ut == "uiv_click":
                result = perception.uivision.click_target(u["target"])
            elif ut == "uiv_type":
                result = perception.uivision.type_text(u["text"])
            else:
                result = "Unknown UI vision action."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- Task Scheduler ---
    if _SCHEDULER_READY:
        s = parse_schedule_request(user_text)
        if s:
            st = s["type"]
            if st == "sched_list":
                result = skills.scheduler.list_tasks()
            elif st == "sched_delete":
                result = skills.scheduler.delete_task(s["name"])
            elif st == "sched_run_now":
                result = skills.scheduler.run_task_now(s["name"])
            elif st == "sched_create":
                result = skills.scheduler.schedule_command(s["name"], s["command"], s["when"])
            else:
                result = "Unknown schedule action."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- Install / download / autofix / self-edit ---
    install_cmd = parse_install_request(user_text)
    if install_cmd:
        itype = install_cmd["type"]
        if itype == "install_package":
            if not _INSTALLER_READY:
                result = "Installer module isn't loaded — can't install packages right now."
            else:
                result = system.installer.install_package(install_cmd["name"], install_cmd.get("manager"))
        elif itype == "download_file":
            if not _INSTALLER_READY:
                result = "Installer module isn't loaded — can't download right now."
            else:
                send_response(f"Downloading {install_cmd['url']}...")
                result = system.installer.download_file(install_cmd["url"])
        elif itype == "run_installer":
            if not _INSTALLER_READY:
                result = "Installer module isn't loaded."
            else:
                result = system.installer.run_installer(install_cmd["path"])
        elif itype == "run_with_autofix":
            if not _CODER_READY:
                result = "Coder module isn't loaded — can't auto-fix."
            else:
                send_response(f"Running with auto-fix: {install_cmd['path']}...")
                result = skills.coder.run_with_autofix(install_cmd["path"])
        elif itype == "self_edit":
            if not _AGENT_READY:
                result = "Agent module isn't loaded — can't self-edit."
            else:
                result = skills.agent.stage_self_edit(install_cmd["module"], install_cmd["change"])
        else:
            result = "Unknown install action."
        send_response(result)
        add_to_memory(PERSONA_NAME, result)
        return

    # --- Voice coding (Pack B): tests, git status, smart commit, project memory ---
    if _DEV_VOICE_READY:
        dev_cmd = parse_dev_command(user_text)
        if dev_cmd:
            dtype = dev_cmd["type"]
            if dtype == "pytest_brief":
                proj = dev_cmd.get("project")
                root = None
                if proj:
                    p = _project.set_current(proj)
                    if not p:
                        result = f"I don't know a project called '{proj}'. Say the path, or 'work on' it first."
                        send_response(result)
                        add_to_memory(PERSONA_NAME, result)
                        return
                    root = p["root"]
                send_response("Running the tests...")
                result = skills.dev_voice.pytest_brief(root)
            elif dtype == "git_brief":
                result = skills.dev_voice.git_brief()
            elif dtype == "smart_commit":
                prep = skills.dev_voice.smart_commit(
                    message=dev_cmd.get("message"),
                    include_untracked=dev_cmd.get("include_untracked", False),
                )
                if prep.get("confirm"):
                    MEM["pending_confirm"] = {
                        "action": "dev_commit",
                        "root": prep["root"],
                        "message": prep["message"],
                        "files": prep.get("files", []),
                        "new_files": prep.get("new_files", []),
                        "include_untracked": prep.get("include_untracked", False),
                    }
                    save_memory(MEM)
                    n = len(prep.get("files", [])) + len(prep.get("new_files", []))
                    result = (f"I'll commit {n} file{'s' if n != 1 else ''} with: "
                              f"\"{prep['message']}\". Say 'yes' to commit, 'no' to cancel.")
                else:
                    result = prep.get("message", "Nothing to commit.")
            elif dtype == "set_current":
                proj = dev_cmd["project"]
                p = _project.set_current(proj)
                if not p:
                    result = f"I couldn't find a project called '{proj}'. Try saying the full path."
                else:
                    result = skills.dev_voice.resume_brief(p["root"])
            elif dtype == "resume_brief":
                result = skills.dev_voice.resume_brief()
            elif dtype == "list_projects":
                result = skills.dev_voice.list_projects_brief()
            else:
                result = "Unknown dev command."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- Coding mode: multi-file projects, project-aware edits, run code ---
    if _CODER_READY:
        coder_cmd = parse_coder_request(user_text)
        if coder_cmd:
            ctype = coder_cmd["type"]
            if ctype == "generate_project":
                send_response(f"Building project at {coder_cmd['root_dir']}...")
                result = skills.coder.generate_project(coder_cmd["spec"], coder_cmd["root_dir"])
            elif ctype == "edit_in_project":
                send_response(f"Editing project at {coder_cmd['root_dir']}...")
                result = skills.coder.edit_in_project(coder_cmd["root_dir"], coder_cmd["change"])
            elif ctype == "run_code":
                send_response(f"Running {coder_cmd['path']}...")
                result = skills.coder.run_code(coder_cmd["path"])
            else:
                result = "Unknown coder action."
            send_response(result)
            add_to_memory(PERSONA_NAME, result)
            return

    # --- Skill registry: teach / list / remove triggers ---
    if _SKILLS_READY:
        skill_cmd = skills.triggers.parse_skill_command(user_text)
        if skill_cmd:
            msg = skills.triggers.handle_skill_command(skill_cmd)
            send_response(msg)
            add_to_memory(PERSONA_NAME, msg)
            return

    # --- Agent job-queue commands (status / cancel / list) ---
    if _JOBS_READY:
        lt_jobs = user_text.lower().strip()
        if re.match(r"^(?:agent\s+(?:status|jobs|list)|list\s+agents|jobs)\s*$", lt_jobs):
            msg = skills.jobs.render_status()
            send_response(msg)
            add_to_memory(PERSONA_NAME, msg)
            return
        m_cancel = re.match(r"^(?:cancel|stop|kill)\s+(?:agent\s+)?([a-f0-9]{8})\s*$", lt_jobs)
        if m_cancel:
            msg = skills.jobs.cancel(m_cancel.group(1))
            send_response(msg)
            add_to_memory(PERSONA_NAME, msg)
            return

    # --- Autonomous agent (multi-step plan/act/observe loop) ---
    if _AGENT_READY:
        agent_goal = parse_agent_request(user_text)
        if agent_goal:
            confirm_prompt = skills.agent.request_run_with_confirmation(agent_goal)
            send_response(confirm_prompt)
            add_to_memory(PERSONA_NAME, confirm_prompt)
            return

    # --- Vision: screen / webcam analysis via Gemini ---
    vision_req = _parse_vision_request(user_text)
    if vision_req:
        source, question = vision_req
        send_response("Looking..." if source == "screen" else "One sec — checking the camera...")
        if source == "screen":
            vmsg = _vision_analyze_screen(_gemini_client, question)
        else:
            vmsg = _vision_analyze_webcam(_gemini_client, question)
        send_response(vmsg)
        add_to_memory(PERSONA_NAME, vmsg)
        return

    # --- Smart-home device control via Home Assistant ---
    # Only consult HA when it's actually configured/reachable. Otherwise
    # HA's "play X" regex would shadow Spotify with a "not connected to HA"
    # message even on devices that have no smart-home setup.
    if _ha_available():
        ha_msg = _ha_command(user_text)
        if ha_msg is not None:
            send_response(ha_msg)
            add_to_memory(PERSONA_NAME, ha_msg)
            return

    # --- Phone bridge via KDE Connect (ring, sms, clipboard, file share) ---
    phone_msg = _kdec_command(user_text)
    if phone_msg is not None:
        send_response(phone_msg)
        add_to_memory(PERSONA_NAME, phone_msg)
        return

    # --- Spotify Connect (play/pause/skip/now playing/volume) ---
    spotify_msg = _spotify_command(user_text)
    if spotify_msg is not None:
        send_response(spotify_msg)
        add_to_memory(PERSONA_NAME, spotify_msg)
        try:
            from integrations.spotify import now_playing_payload
            np = now_playing_payload()
            _state_server.set_now_playing(np)
            if np:
                _state_server.set_action("dock_orb")
        except Exception:
            pass
        return

    sysc = parse_system_control(user_text)
    if sysc:
        if sysc["type"] == "open": msg = open_target(sysc["target"])
        elif sysc["type"] == "close": msg = close_target(sysc["target"])
        else: msg = queue_dangerous(sysc["target"])
        send_response(msg)
        return
    
    # --- Resolve ambiguous follow-ups and corrections for volume/brightness ---
    lt_check = user_text.lower().strip()
    last_sys = MEM.get("last_system_command")

    correction_m = re.match(
        r"(?:zendaya,?\s*)?(?:i\s+(?:meant|said|want)|no,?\s*(?:i\s+(?:meant|said|want))?)\s*"
        r"(brightness|volume|sound|audio)",
        lt_check
    )
    if not correction_m:
        correction_m = re.match(
            r"(?:zendaya,?\s*)?(brightness|volume)\s+not\s+(volume|brightness)",
            lt_check
        )
    if correction_m:
        intended = correction_m.group(1).strip()
        if intended in ("brightness",):
            sys_result = adjust_brightness("down", 15)
        else:
            sys_result = adjust_volume("down", 5)
        set_last_system_command(sys_result)
        send_response(f"My mistake. {sys_result}")
        return

    if last_sys in ("volume", "brightness"):
        followup_m = re.match(
            r"(?:zendaya,?\s*)?(?:set|reduce|lower|increase|raise|turn|change|put|make)\s+"
            r"(?:it\s+)?(?:to\s+)?(\d+)%?\s*$",
            lt_check
        )
        if followup_m:
            level = int(followup_m.group(1))
            if last_sys == "brightness":
                sys_result = set_brightness(level)
            else:
                sys_result = set_volume(level)
            set_last_system_command(sys_result)
            send_response(sys_result)
            return

        followup_down = re.search(
            r"\b(reduce|lower|turn\s*(?:it\s+)?down|decrease|dim|darker|quieter)\b", lt_check
        )
        followup_up = re.search(
            r"\b(increase|raise|turn\s*(?:it\s+)?up|louder|higher|brighter|brighten)\b", lt_check
        )
        has_subject = re.search(
            r"\b(volume|sound|audio|brightness|screen|display|light)\b", lt_check
        )
        if not has_subject and (followup_down or followup_up):
            direction = "down" if followup_down else "up"
            if last_sys == "brightness":
                sys_result = adjust_brightness(direction, 15)
            else:
                sys_result = adjust_volume(direction, 5)
            set_last_system_command(sys_result)
            send_response(sys_result)
            return

    # --- System access commands (files, email, volume, screenshots, etc.) ---
    sys_result = handle_system_access(user_text)
    if sys_result == "__ask_folder_name__":
        MEM["pending_action"] = {"type": "create_folder", "step": "need_name"}
        save_memory(MEM)
        send_response("Sure! What would you like to name the folder?")
        return
    if sys_result == "__ask_file_name__":
        MEM["pending_action"] = {"type": "create_file", "step": "need_name"}
        save_memory(MEM)
        last = MEM.get("last_action")
        if last and last["type"] == "folder":
            send_response(f"What should I name the file? (I'll put it in '{last['name']}')")
        else:
            send_response("What should I name the file?")
        return
    if sys_result is not None:
        if sys_result.startswith("Folder created:"):
            folder_path = sys_result.replace("Folder created: ", "").strip()
            set_last_action("folder", os.path.basename(folder_path), folder_path)
        elif sys_result.startswith("File created:"):
            file_path = sys_result.replace("File created: ", "").strip()
            set_last_action("file", os.path.basename(file_path), file_path)
        elif sys_result.startswith("Renamed to"):
            pass  # rename_item doesn't give us the full path, keep existing last_action
        set_last_system_command(sys_result)
        send_response(sys_result)
        return

    # --- If no command, handle as conversational query ---
    search_context = None
    if should_auto_search(user_text):
        send_response("Searching the network for you...")
        search_context = tavily_search(user_text)

    ai_text = gemini_reply(user_text, search_context)
    
    add_to_memory(PERSONA_NAME, ai_text)
    send_response(ai_text)
    summarize_memory()

_WORKFLOW_RUNNING = False


def _llm_split_workflow(user_text: str) -> List[str]:
    """Use Gemini to break a multi-step command into ordered atomic steps."""
    if not _GEMINI_READY or not is_connected():
        return []
    prompt = (
        "Split the following user command into an ordered JSON list of short, atomic single-action "
        "instructions a desktop assistant can execute one at a time. Preserve the user's original "
        "phrasing for each step. Do not add steps the user didn't ask for. Return ONLY a JSON array "
        "of strings, no commentary.\n\n"
        f"Command: {user_text}\n\nJSON:"
    )
    try:
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = (resp.text or "").strip()
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return []
        steps = json.loads(raw[start:end + 1])
        return [s.strip() for s in steps if isinstance(s, str) and s.strip()]
    except Exception:
        return []


def _regex_split_workflow(user_text: str) -> List[str]:
    """Fallback splitter using temporal connectors."""
    parts = re.split(
        r"\s+(?:and then|then|after that|once that[\'\u2019]?s done|after|next|followed by|and)\s+",
        user_text,
        flags=re.IGNORECASE,
    )
    return [p.strip(" ,.;") for p in parts if p and p.strip(" ,.;")]


def handle_complex_workflow(user_text: str) -> str:
    """
    Multi-step orchestrator. Uses Gemini to decompose the request into atomic
    steps, then routes each step back through handle_user_command so every
    parser (file gen, system control, system access, etc.) handles its own step.
    """
    global _WORKFLOW_RUNNING
    if _WORKFLOW_RUNNING:
        return ""

    steps = _llm_split_workflow(user_text)
    if len(steps) < 2:
        steps = _regex_split_workflow(user_text)
    if len(steps) < 2:
        return ""

    _WORKFLOW_RUNNING = True
    try:
        send_response(f"Got it — running {len(steps)} steps.")
        for i, step in enumerate(steps, 1):
            print(f"\n[Step {i}/{len(steps)}] {step}")
            try:
                handle_user_command(step)
            except Exception as e:
                send_response(f"Step {i} failed: {e}")
                log_event("workflow_error", str(e), {"step": step})
            time.sleep(0.4)
        return f"Workflow complete — {len(steps)} steps executed."
    finally:
        _WORKFLOW_RUNNING = False

# -----------------------
# Main loop
# -----------------------
def summarize_recent_activity() -> str:
    """Use Gemini to summarize what the user was recently working on."""
    files = scan_recent_activity(hours=24, max_files=15)
    if not files:
        return "I don't see any recent file activity in the past day."

    if not _GEMINI_READY:
        names = ", ".join(f["name"] for f in files[:5])
        return f"You recently touched: {names}"

    file_list = "\n".join(
        f"- '{f['name']}' in '{f['location']}' (last touched: {f['modified']})"
        for f in files
    )
    prompt = (
        "Based on these recently modified files on the user's PC, generate a concise, "
        "one-or-two-sentence summary of what they were likely working on. Infer the activity "
        "(e.g., 'working on a report', 'editing code', 'managing finances').\n\n"
        f"Files:\n{file_list}\n\nSummary:"
    )
    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception:
        names = ", ".join(f["name"] for f in files[:5])
        return f"You recently touched: {names}"


# ── Clean shutdown (headless mode) ──────────────────────
_SHUTDOWN = threading.Event()


def request_shutdown() -> None:
    """Trigger a clean, intentional exit from any quit trigger (voice / HUD /quit /
    Quit shortcut). Sets the headless wait's event so __main__ falls through and the
    process exits with code 0 — the supervisor reads exit-0 as 'do not restart'."""
    log_event("shutdown", "Shutdown requested", {})
    _SHUTDOWN.set()


def main():
    user_name = MEM.get("user_name")
    welcome_message = f"Welcome back, {user_name}." if user_name else "Welcome back."

    weather = get_weather_greeting()
    greeting = f"{welcome_message} My systems are online and ready."
    if weather:
        greeting += f" {weather}"

    if not is_connected():
        greeting += " Heads up — I'm offline right now, so search and AI features will be limited."

    send_response(greeting)
    log_event("startup", greeting, {"user": user_name, "online": is_connected()})

    EXIT_COMMANDS = ["exit", "quit", "bye", "goodbye", "farewell", "deactivate"]

    try:
        while True:
            user_text = input("\nYou: ").strip()

            if not user_text:
                continue

            close_matches = difflib.get_close_matches(user_text.lower(), EXIT_COMMANDS, n=1, cutoff=0.7)
            if close_matches:
                bye = "Farewell. Don’t cause trouble without me."
                send_response(bye)
                log_event("shutdown", "User exited", {})
                break

            try:
                handle_user_command(user_text)
            except _ZendayaExit:
                log_event("shutdown", "User deactivated assistant", {})
                break
            except re.error as e:
                send_response(
                    "Sorry — I tripped over a special character (often a Windows path "
                    "with a backslash) while parsing that. Could you rephrase, or wrap "
                    "the path in quotes?"
                )
                log_event("regex_error", f"re.error: {e}", {"input": user_text})
            except Exception as e:
                err_msg = f"Something went wrong handling that: {e}"
                send_response(err_msg)
                log_event("error", err_msg, {"input": user_text})

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        bye = "Deactivating. Talk to you later."
        send_response(bye)
        log_event("shutdown", "Keyboard interrupt", {})
        time.sleep(2)
    finally:
        print("System shutdown complete.")

if __name__ == "__main__":
    from voice.listener_v2 import start_voice_listener, diagnostics
    print(diagnostics())
    start_voice_listener()

    from skills.alerts import start_alerts
    start_alerts()
    print("Proactive alerts active.")

    try:
        import skills.proactive
        skills.proactive.start(
            send_response,
            lambda: analyze_system_emotion(
                {"gemini": _GEMINI_READY, "tts": _TTS_ENGINE is not None}
            ),
            MEM,
        )
        print("🧭 Proactive check-ins active.")
    except Exception as _pro_err:
        print(f"(Proactive check-ins unavailable: {_pro_err})")

    # ─── Perception (face presence + gestures) ───
    _vision_on = bool(MEM.get("vision_enabled", False))
    _gestures_on = bool(MEM.get("gestures_enabled", False))
    if not (_vision_on or _gestures_on):
        print("👁️  Perception standby (vision + gestures off — say 'turn on vision' to enable).")
    else:
        try:
            import perception.camera as _perception

            def _on_gesture(name: str):
                try:
                    log_event("gesture", name, {})
                except Exception:
                    pass
                print(f"[gesture] {name}")
                if name == "Thumb_Up":
                    if MEM.get("pending_confirm"):
                        handle_user_command("yes")
                    else:
                        send_response("Got it.")
                elif name == "Open_Palm":
                    stop_speaking()
                elif name == "Closed_Fist":
                    if MEM.get("pending_confirm"):
                        MEM["pending_confirm"] = None
                        save_memory(MEM)
                        send_response("Cancelled.")
                elif name == "Victory":
                    try:
                        from perception.vision import describe_screen
                        send_response(describe_screen("What's on screen right now?"))
                    except Exception as _e:
                        send_response(f"Couldn't read the screen: {_e}")
                # Pointing_Up: reserved — no action wired yet.

            _perception.set_enabled(
                face=_vision_on,
                gestures=_gestures_on,
            )
            _perception.start(on_gesture=_on_gesture)
            if _state_server is not None:
                _state_server.set_perception_providers(
                    face=_perception.get_face,
                    last_gesture=_perception.get_last_gesture,
                )
            print("👁️  Perception active (face + gestures).")
        except Exception as _per_err:
            print(f"(Perception unavailable: {_per_err})")

    # ─── Telemetry feed for HUD ───
    if _state_server is not None:
        try:
            import psutil as _psutil

            def _telemetry() -> dict:
                try:
                    cpu = _psutil.cpu_percent(interval=None)
                except Exception:
                    cpu = 0.0
                try:
                    mem_p = _psutil.virtual_memory().percent
                except Exception:
                    mem_p = 0.0
                try:
                    mood = analyze_system_emotion(
                        {"gemini": _GEMINI_READY, "tts": _TTS_ENGINE is not None}
                    )
                except Exception:
                    mood = "neutral"
                vision_active = False
                gestures_active = False
                last_gesture = {"name": "none", "ts": 0.0}
                try:
                    import perception.camera as _per
                    state = _per.is_active()
                    vision_active = bool(state.get("face")) and MEM.get("vision_enabled", True)
                    gestures_active = bool(state.get("gestures")) and MEM.get("gestures_enabled", True)
                    last_gesture = _per.get_last_gesture()
                except Exception:
                    pass
                # mic_level: latest TTS amplitude proxies as Zendaya's voice level;
                # a separate mic-input level would need the listener to expose it.
                mic_level = 0.0
                try:
                    mic_level = float(_state_server.get_mouth().get("level", 0.0))
                except Exception:
                    pass
                return {
                    "cpu": cpu,
                    "mem": mem_p,
                    "mic_level": mic_level,
                    "mood": mood,
                    "vision_active": vision_active,
                    "gestures_active": gestures_active,
                    "hud_enabled": MEM.get("hud_enabled", True),
                    "last_gesture": last_gesture,
                    "online": is_connected(),
                    "user_name": MEM.get("user_name") or "",
                    "language": MEM.get("language", "english"),
                }

            _state_server.set_telemetry_provider(_telemetry)
            print("📟 Telemetry feed live.")
        except Exception as _tel_err:
            print(f"(Telemetry unavailable: {_tel_err})")

        # ── Now-playing poll loop — pushes Spotify/local music state to the HUD.
        def _now_playing_loop():
            from integrations.spotify import now_playing_payload
            last_state = None
            last_track = None
            while True:
                try:
                    np = now_playing_payload()
                    key = (np["track"], np["is_playing"]) if np else None
                    if key != last_state:
                        _state_server.set_now_playing(np)
                        if np and np["track"] != last_track:
                            _state_server.set_action("dock_orb")
                            last_track = np["track"]
                        elif np is None:
                            _state_server.set_action("undock_orb")
                            last_track = None
                        last_state = key
                except Exception:
                    pass
                time.sleep(2.0)

        threading.Thread(target=_now_playing_loop, daemon=True).start()

    # Start the state server so the Godot frontend can poll status and
    # post chat messages. Failure to start (e.g. fastapi/uvicorn missing)
    # falls back to console-only operation.
    if _state_server is not None:
        def _bridge_user_message(msg: str):
            try:
                handle_user_command(msg)
            except Exception as e:
                send_response(f"Something went wrong handling that: {e}")
                log_event("error", str(e), {"input": msg, "src": "godot"})

        # Window watcher + window-control dispatcher for the Godot side.
        try:
            import perception.windows as _wwatcher
        except Exception as _ww_err:
            print(f"(Window watcher unavailable: {_ww_err})")
            _wwatcher = None

        from system.access import (
            focus_window as _focus_window,
            minimize_window as _minimize_window,
            maximize_window as _maximize_window,
            close_window as _close_window,
        )

        def _window_control(action: str, title: str) -> str:
            if action == "focus":
                return _focus_window(title)
            if action == "minimize":
                return _minimize_window(title)
            if action == "maximize":
                return _maximize_window(title)
            if action == "close":
                return _close_window(title)
            return f"Unknown window action: {action}"

        try:
            _state_server.start(
                on_chat=_bridge_user_message,
                on_chat_sync=_bridge_user_message_sync,
                on_window_control=_window_control,
                window_get_snapshot=(_wwatcher.get_snapshot if _wwatcher else None),
                window_pop_events=(_wwatcher.pop_events if _wwatcher else None),
                on_quit=request_shutdown,
            )
            print("🪟 State server: http://127.0.0.1:7475")
            import os as _os
            if _os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip():
                _bh = _os.environ.get("ZENDAYA_BIND_HOST", "127.0.0.1")
                print(f"📱 Mobile API ready at /api/v1 (bind {_bh}; token set).")
            else:
                print("📱 Mobile API disabled (set ZENDAYA_MOBILE_TOKEN in .env to enable).")
        except Exception as _ss_err:
            print(f"(State server unavailable: {_ss_err})")

        if _wwatcher is not None:
            try:
                _wwatcher.start()
                print("👁  Window watcher active.")
            except Exception as _ww_err:
                print(f"(Window watcher failed to start: {_ww_err})")
    else:
        print("(State server module not loaded — Godot frontend will not connect.)")

    if _SKILLS_READY:
        try:
            skills.triggers.start()
            n = len(skills.triggers.list_skills())
            print(f"🎯 Skills active ({n} loaded).")
        except Exception as _sk_err:
            print(f"(Skills watcher failed to start: {_sk_err})")

    if _JOURNAL_READY:
        try:
            skills.journal.start()
            print("📓 Project journal active.")
        except Exception as _jr_err:
            print(f"(Journal failed to start: {_jr_err})")

    if _SCREEN_READY and MEM.get("screen_awareness_enabled", False):
        try:
            _screen.start()
            print("🖥  Screen awareness active.")
        except Exception as _sa_err:
            print(f"(Screen awareness failed to start: {_sa_err})")

    if _HOTKEY_READY:
        try:
            _hotkey.start()
        except Exception as _hk_err:
            print(f"(Hotkey failed to start: {_hk_err})")

    if "--headless" in sys.argv:
        print("Zendaya running headless — voice + HUD are the input methods.")
        _SHUTDOWN.wait()
        print("System shutdown complete.")
    else:
        main()
