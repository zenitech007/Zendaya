"""
greeting.py
Cinematic holographic greeting with GUI hologram window (Tkinter),
audio playback synced to exact audio duration (from ElevenLabs),
and graceful fallback to pyttsx3.
"""

import asyncio
import datetime
import getpass
import json
import math
import os
import random
import sys
import tempfile
import threading
import multiprocessing
import time
from pathlib import Path
from typing import Dict, Callable, Awaitable, Optional

# Optional libs
try:
    from colorama import Fore, Style, init as _color_init
    _color_init(autoreset=True)
except Exception:
    class _Fake:
        def __getattr__(self, _): return ""
    Fore = Style = _Fake()

try:
    import tkinter as tk
    from tkinter import ttk
    _HAS_TK = True
except Exception:
    _HAS_TK = False

# Playback library - playsound is simple and blocks until finished (works on Windows)
try:
    from playsound import playsound
    _HAS_PLAYSOUND = True
except Exception:
    _HAS_PLAYSOUND = False

# Local helpers from your project
from zendaya_backend.agent.tools.network_check import is_connected
from zendaya_backend.agent.tools.emotion_engine import analyze_system_emotion
from zendaya_backend.agent.tools.memory_logger import log_event
from zendaya_backend.core.config import settings

# fallback TTS
try:
    import pyttsx3
    _HAS_PYTTSX3 = True
except Exception:
    _HAS_PYTTSX3 = False

LAST_GREET_PATH = Path("last_greet.json")
STARTUP_WAV = Path("startup.wav")

# ------------------------------------------------
# Tiny Tk GUI Hologram
# ------------------------------------------------
class TkHologram:
    def __init__(self, emotion: str = "focused", title: str = "Zendaya"):
        if not _HAS_TK:
            raise RuntimeError("Tkinter not available")
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("420x420")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # draw a simple face using canvas shapes
        self.left_eye = self.canvas.create_oval(110, 120, 160, 170, fill="#22DDFF", outline="")
        self.right_eye = self.canvas.create_oval(260, 120, 310, 170, fill="#22DDFF", outline="")
        self.mouth = self.canvas.create_arc(150, 200, 270, 260, start=0, extent=130, fill="#22DDFF", outline="")
        self.subtitle = self.canvas.create_text(210, 340, text="", fill="#DDEEFF", font=("Helvetica", 12), anchor="center")
        self.pulse_circle = self.canvas.create_oval(80, 60, 340, 320, outline="#22DDFF", width=2)
        self.running = False
        self.closed = False

    def _on_close(self):
        self.closed = True
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def show(self):
        self.running = True
        threading.Thread(target=self.root.mainloop, daemon=True).start()

    def destroy(self):
        try:
            self._on_close()
        except Exception:
            pass

    def set_subtitle(self, text: str):
        try:
            self.canvas.itemconfig(self.subtitle, text=text)
        except Exception:
            pass

    def pulse_eyes(self, amplitude: float):
        # amplitude 0..1 -> scale eye radii and color intensity
        r_base = 25
        r = int(r_base * (1.0 + amplitude * 0.9))
        def set_eye(id, cx, cy):
            self.canvas.coords(id, cx - r, cy - r, cx + r, cy + r)
            blue = int(200 + amplitude * 55)
            color = f"#{0:02x}{blue:02x}{255:02x}"
            try:
                self.canvas.itemconfig(id, fill=color)
            except Exception:
                pass
        set_eye(self.left_eye, 135, 145)
        set_eye(self.right_eye, 285, 145)

    def mouth_shape(self, openness: float):
        # openness 0..1 controls arc extent
        extent = 80 + int(80 * openness)
        try:
            self.canvas.itemconfig(self.mouth, extent=extent)
        except Exception:
            pass

    def pulse_glow(self, t: float):
        # pulse outline width over time
        width = 2 + int(3 * (0.5 + 0.5 * math.sin(t * 3.0)))
        try:
            self.canvas.itemconfig(self.pulse_circle, width=width)
        except Exception:
            pass

# ------------------------------------------------
# Terminal fallback frame (simple)
# ------------------------------------------------
def _terminal_face_frame(amplitude: float, emotion: str = "focused"):
    os.system("cls" if os.name == "nt" else "clear")
    eye = "●" if amplitude < 0.3 else "✦" if amplitude > 0.7 else "○"
    mouth = "___" if amplitude < 0.3 else "━━━" if amplitude > 0.6 else "‾‾‾"
    print(Fore.CYAN + "\n    ╭────────╮")
    print(f"   │  {eye}   {eye}  │")
    print(f"   │    ╳    │")
    print(f"   │  {mouth}  │")
    print("    ╰────────╯\n" + Style.RESET_ALL)

# ------------------------------------------------
# Play audio file blocking (in a thread)
# ------------------------------------------------
def _play_audio_blocking(path: str):
    # try playsound (blocks until finished)
    if _HAS_PLAYSOUND:
        try:
            playsound(path)
            return
        except Exception:
            pass

    # fallback: on Windows use winsound.PlaySound (works for WAV only)
    try:
        import winsound
        if path.lower().endswith(".wav"):
            winsound.PlaySound(path, winsound.SND_FILENAME)
            return
    except Exception:
        pass

    # last resort: attempt OS open (will not block reliably)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform.startswith("darwin"):
            os.system(f"open {path!r}")
        else:
            os.system(f"xdg-open {path!r} >/dev/null 2>&1 &")
    except Exception:
        pass

# ------------------------------------------------
# Capture amplitude optionally (sounddevice) or simulate
# ------------------------------------------------
_HAS_CAPTURE = False
try:
    import sounddevice as sd
    import numpy as np
    _HAS_CAPTURE = True
except Exception:
    _HAS_CAPTURE = False

async def _simulated_amplitude_loop(duration: float, gui: Optional[TkHologram], emotion: str):
    start = time.time()
    while time.time() - start < duration:
        amp = max(0.02, random.random() * 0.9)
        if gui:
            gui.pulse_eyes(amp)
            gui.mouth_shape(amp)
            gui.pulse_glow(time.time())
        else:
            _terminal_face_frame(amp, emotion)
        await asyncio.sleep(0.12)

# If capture available, create an async generator reading amplitude
async def _captured_amplitude_loop(duration: float, gui: Optional[TkHologram], emotion: str):
    if not _HAS_CAPTURE:
        return await _simulated_amplitude_loop(duration, gui, emotion)

    amplitude = {"val": 0.0}
    def callback(indata, frames, time_info, status):
        try:
            amplitude["val"] = float(np.linalg.norm(indata)) / (frames * indata.shape[1]) * 10.0
            amplitude["val"] = max(0.0, min(1.0, amplitude["val"]))
        except Exception:
            amplitude["val"] = 0.0

    stream = sd.InputStream(callback=callback, channels=1)
    try:
        stream.start()
    except Exception:
        # fallback
        await _simulated_amplitude_loop(duration, gui, emotion)
        return

    start = time.time()
    try:
        while time.time() - start < duration:
            amp = amplitude["val"]
            if gui:
                gui.pulse_eyes(amp)
                gui.mouth_shape(amp)
                gui.pulse_glow(time.time())
            else:
                _terminal_face_frame(amp, emotion)
            await asyncio.sleep(0.10)
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

# ------------------------------------------------
# Run TTS + visuals in sync
# ------------------------------------------------
async def _run_tts_and_visual_sync(
    message: str,
    emotion: str,
    voice_service_obj,
    voice_id: Optional[str],
    gui: Optional[TkHologram],
    approximate_duration: float = 6.5
):
    """
    1) Asks voice_service to synthesize audio (if available) and return local path+duration
    2) Plays it (blocking call inside thread)
    3) Runs amplitude-driven GUI animation for exactly the returned duration
    4) Falls back to pyttsx3 if voice_service not available
    """
    # If voice_service_obj exists and has synthesize_with_emotion, call it
    file_info = None
    if voice_service_obj and hasattr(voice_service_obj, "synthesize_with_emotion"):
        try:
            # synthesize_with_emotion is async and already returns {"path":..., "duration": ...}
            file_info = await voice_service_obj.synthesize_with_emotion(message, emotion, voice_id)
        except Exception as e:
            print(f"(voice synth error: {e})")
            file_info = None

    # If we got a file and path, use that duration; else fallback to approximate duration
    if file_info and isinstance(file_info, dict) and file_info.get("path"):
        audio_path = file_info["path"]
        duration = float(file_info.get("duration", approximate_duration))
        # start audio playback in background thread (blocking play)
        audio_thread = threading.Thread(target=_play_audio_blocking, args=(audio_path,), daemon=True)
        audio_thread.start()
        # run amplitude-driven visuals for `duration`
        try:
            if _HAS_CAPTURE:
                await _captured_amplitude_loop(duration, gui, emotion)
            else:
                await _simulated_amplitude_loop(duration, gui, emotion)
        except asyncio.CancelledError:
            pass
        # ensure audio thread finished (give it small grace)
        audio_thread.join(timeout=1.0)
        return

    # Fallback: no ElevenLabs audio -> offline pyttsx3 (if available)
    if _HAS_PYTTSX3:
        def _py_play():
            try:
                engine = pyttsx3.init()
                # choose a female voice if available
                vlist = engine.getProperty("voices")
                sel = next((v.id for v in vlist if "female" in v.name.lower()), vlist[0].id)
                engine.setProperty("voice", sel)
                engine.setProperty("rate", 165)
                engine.setProperty("volume", 1.0)
                engine.say(message)
                engine.runAndWait()
            except Exception as e:
                print(f"(pyttsx3 error: {e})")

        # run both in parallel (visual + tts)
        t = threading.Thread(target=_py_play, daemon=True)
        t.start()
        # run visuals for approximate_duration
        try:
            if _HAS_CAPTURE:
                await _captured_amplitude_loop(approximate_duration, gui, emotion)
            else:
                await _simulated_amplitude_loop(approximate_duration, gui, emotion)
        except asyncio.CancelledError:
            pass
        t.join(timeout=0.5)
        return

    # Final fallback: no TTS available; show visuals for duration and return
    await _simulated_amplitude_loop(approximate_duration, gui, emotion)
    return

# ------------------------------------------------
# Public greet_user entrypoint
# ------------------------------------------------
async def greet_user(
    status: Dict[str, bool],
    recovery_map: Dict[str, Callable[[], Awaitable[bool]]],
    voice_service_obj=None,
    voice_id: Optional[str] = None,
    preferred_mode: Optional[str] = None
):
    username = getpass.getuser().capitalize()
    today = datetime.date.today().isoformat()

    # once-per-day guard
    try:
        if LAST_GREET_PATH.exists():
            payload = json.loads(LAST_GREET_PATH.read_text())
            if payload.get("date") == today:
                return
    except Exception:
        pass

    # pick mode randomly unless forced
    mode = preferred_mode or random.choice(["minimal", "cinematic", "hybrid"])
    emotion = analyze_system_emotion(status)
    # Terminal boot (always)
    try:
        print(Fore.CYAN + "\n[ZENDAYA] Initiating holographic bootstrap..." + Style.RESET_ALL)
        # small typewriter lines
        _print_animated = lambda s: sys.stdout.write(s + "\n")  # simplified print for boot
        _print_animated(f"  • Mode: {mode}")
        _print_animated(f"  • Emotion core: {emotion}")
        time.sleep(0.3)
    except Exception:
        pass

    # prepare GUI hologram if cinematic/hybrid and tkinter available
    gui = None
    gui_proc = None
    if mode in ("cinematic", "hybrid") and _HAS_TK:
        try:
            def launch_gui_proc():
                g = TkHologram(emotion=emotion)
                g.show()
                g.root.mainloop()

            gui_proc = multiprocessing.Process(target=launch_gui_proc)
            gui_proc.start()
            await asyncio.sleep(0.8)
        except Exception as e:
            print(f"(GUI init error: {e})")
            gui_proc = None

    # build greeting text
    hour = datetime.datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    greeting_texts = {
        "minimal": f"Good {part}, {username}. All systems are online and ready.",
        "cinematic": f"Hello {username}. Systems online and calibrated. Engage.",
        "hybrid": f"Welcome back {username}. Initiating workflows and integrations."
    }
    greeting_line = greeting_texts.get(mode, greeting_texts["minimal"])

    # print status summary
    online = [k for k, v in status.items() if v]
    offline = [k for k, v in status.items() if not v]
    print(Fore.CYAN + f"[STATUS] online: {online} | offline: {offline}" + Style.RESET_ALL)

    # attempt auto-recovery for offline
    if offline and recovery_map:
        print(Fore.YELLOW + "[RECOVERY] attempting repairs..." + Style.RESET_ALL)
        for svc in offline:
            fn = recovery_map.get(svc)
            if fn:
                try:
                    ok = await fn()
                    print(f"  {'✅' if ok else '❌'} {svc}")
                except Exception as e:
                    print(f"  ❌ {svc} recovery error: {e}")

    # speak + visuals sync
    try:
        approx = 7.0
        await _run_tts_and_visual_sync(greeting_line, emotion, voice_service_obj, voice_id, gui, approx)
    except Exception as e:
        print(f"(greeting playback error: {e})")

    # persist last greet
    try:
        LAST_GREET_PATH.write_text(json.dumps({"date": today}))
    except Exception:
        pass

    # keep GUI visible shortly then destroy
    if "gui_proc" in locals() and gui_proc:
        await asyncio.sleep(1.0)
        gui_proc.terminate()

    # final log
    try:
        log_event("greeting", f"Greeted {username} mode={mode} emotion={emotion}", {"offline": offline})
    except Exception:
        pass

