"""
Audio tools for Zendaya hologram lip-sync and playback.
Extracts amplitudes from audio and prepares base64 audio for playback in the hologram.
"""

import io
import base64
import numpy as np
from pydub import AudioSegment


def extract_amplitudes_from_bytes(audio_bytes: bytes, chunk_ms: int = 40):
    """
    Convert raw MP3/WAV bytes into a sequence of amplitude (0–1) values for lip sync.
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    if audio.channels > 1:
        samples = samples.reshape((-1, audio.channels)).mean(axis=1)
    samples /= np.max(np.abs(samples)) + 1e-6

    chunk_size = int(audio.frame_rate * (chunk_ms / 1000.0))
    amplitudes = []
    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i + chunk_size]
        amp = float(np.sqrt(np.mean(chunk ** 2)))
        amplitudes.append(round(amp, 3))
    return amplitudes


def audio_bytes_to_base64(audio_bytes: bytes, mime_type="audio/mpeg") -> str:
    """
    Convert audio bytes to base64 for HTML playback via JS `Audio()`.
    """
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"
