"""
zendaya_hotkey — global push-to-talk hotkey.

Hold Win+` (backtick) to record. Release to transcribe + dispatch via the
existing zendaya_voice_listener pipeline (Whisper → Google fallback).

This is a SECOND audio path that bypasses Porcupine wake-word detection —
useful when:
  - the wake-word file isn't trained yet
  - the mic is too noisy / wake word is missing the user
  - the user wants to talk fast without saying the name

Public API:
    start() -> None
    stop() -> None
    is_running() -> bool
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np


try:
    import keyboard
    _KB_READY = True
except Exception as e:
    _KB_READY = False
    _KB_ERR = str(e)

try:
    import sounddevice as sd
    _SD_READY = True
except Exception as e:
    _SD_READY = False
    _SD_ERR = str(e)


HOTKEY = "windows+`"
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_RECORD_S = 30.0


_LOCK = threading.Lock()
_STARTED = False
_RECORDING = False
_RECORD_BUF: list = []
_STREAM = None
_RECORD_START_TS: float = 0.0


def _z():
    import zendaya as _zmod
    return _zmod


def _voice():
    import zendaya_voice_listener_v2 as _vmod
    return _vmod


def is_running() -> bool:
    return _STARTED


def _audio_callback(indata, frames, time_info, status):
    if not _RECORDING:
        return
    try:
        flat = indata[:, 0] if indata.ndim > 1 else indata
        _RECORD_BUF.append(flat.copy())
    except Exception:
        pass


def _open_stream():
    global _STREAM
    if _STREAM is not None:
        return _STREAM
    try:
        _STREAM = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=480,  # 30 ms @ 16 kHz
            callback=_audio_callback,
        )
        _STREAM.start()
        return _STREAM
    except Exception as e:
        print(f"(hotkey: failed to open mic: {e})")
        _STREAM = None
        return None


def _start_recording():
    global _RECORDING, _RECORD_BUF, _RECORD_START_TS
    with _LOCK:
        if _RECORDING:
            return
        if _open_stream() is None:
            return
        _RECORD_BUF = []
        _RECORDING = True
        _RECORD_START_TS = time.time()
    try:
        _z().send_response("🎙  PTT — listening...")
    except Exception:
        pass


def _stop_recording():
    global _RECORDING
    with _LOCK:
        if not _RECORDING:
            return
        _RECORDING = False
        chunks = list(_RECORD_BUF)
        duration = time.time() - _RECORD_START_TS
    if not chunks:
        try:
            _z().send_response("(PTT — no audio)")
        except Exception:
            pass
        return
    if duration < 0.3:
        # Too short — likely an accidental tap.
        try:
            _z().send_response("(PTT — tap too short)")
        except Exception:
            pass
        return
    audio = np.concatenate(chunks)
    threading.Thread(
        target=_transcribe_and_dispatch,
        args=(audio,),
        daemon=True,
        name="zendaya-hotkey-dispatch",
    ).start()


def _transcribe_and_dispatch(audio_int16: np.ndarray) -> None:
    try:
        v = _voice()
        text = v._transcribe(audio_int16)
    except Exception as e:
        try:
            _z().send_response(f"(PTT transcribe failed: {e})")
        except Exception:
            pass
        return
    cleaned = (text or "").strip()
    if not cleaned:
        try:
            _z().send_response("(PTT — couldn't transcribe)")
        except Exception:
            pass
        return
    try:
        z = _z()
        z.send_response(f"[ptt] you: {cleaned}")
        z.handle_user_command(cleaned)
    except Exception as e:
        print(f"(hotkey dispatch error: {e})")


def _safety_watchdog():
    """If a key-up event is missed, cap recording at MAX_RECORD_S."""
    while _STARTED:
        time.sleep(1.0)
        with _LOCK:
            recording = _RECORDING
            elapsed = time.time() - _RECORD_START_TS if recording else 0.0
        if recording and elapsed > MAX_RECORD_S:
            print("(hotkey: max recording duration hit — stopping)")
            _stop_recording()


def start() -> None:
    global _STARTED
    if _STARTED:
        return
    if not _KB_READY:
        print(f"(hotkey disabled — keyboard package missing: {_KB_ERR})")
        print("  pip install keyboard")
        return
    if not _SD_READY:
        print(f"(hotkey disabled — sounddevice missing: {_SD_ERR})")
        return
    try:
        keyboard.on_press_key("`", lambda e: _on_key_event(True))
        keyboard.on_release_key("`", lambda e: _on_key_event(False))
    except Exception as e:
        print(f"(hotkey: failed to bind '`': {e})")
        return
    _STARTED = True
    threading.Thread(target=_safety_watchdog, daemon=True, name="zendaya-hotkey-wd").start()
    print(f"⌨  PTT hotkey active — hold Win+` to talk.")


def _on_key_event(pressed: bool) -> None:
    """Only fire when Win is also held — cheap modifier check."""
    try:
        win_held = keyboard.is_pressed("windows")
    except Exception:
        win_held = False
    if pressed:
        if win_held:
            _start_recording()
    else:
        # Release fires even if Win was let go first; stop if we were recording.
        if _RECORDING:
            _stop_recording()


def stop() -> None:
    global _STARTED, _STREAM
    _STARTED = False
    try:
        keyboard.unhook_all()
    except Exception:
        pass
    if _STREAM is not None:
        try:
            _STREAM.stop()
            _STREAM.close()
        except Exception:
            pass
        _STREAM = None
