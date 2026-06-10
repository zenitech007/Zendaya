"""
zendaya_visemes — cheap text → timed viseme schedule for VRM lipsync.

Five output blendshape weights aligned with common VRM mouth shapes:
    aa   open jaw            (a)
    ih   relaxed wide        (i, e closed)
    ee   smile-spread        (e long, ay)
    oh   rounded mid         (o)
    ou   tight rounded       (u, w, m, b, p)

We don't do real phoneme alignment — instead each character of the spoken
text is mapped to one of those visemes (or "rest"), and durations are
spread evenly across an estimated speech duration. While ElevenLabs streams
PCM, the playback loop calls `player.current()` ~10–40 Hz to grab the
currently active blendshape weights, modulated by audio amplitude so
silent gaps don't keep the mouth open.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Tuple


VISEMES = ("aa", "ih", "ee", "oh", "ou")
_REST = "rest"

# Per-character viseme. Anything not in this map is treated as a rest.
# Lower-cased before lookup.
_LETTER_TO_VISEME = {
    "a": "aa",
    "e": "ee",
    "i": "ih",
    "o": "oh",
    "u": "ou",
    "y": "ih",
    # Closed-lip-ish consonants → ou shape
    "m": "ou",
    "b": "ou",
    "p": "ou",
    "w": "ou",
    # Lip-touching fricatives → ih (slight smile)
    "f": "ih",
    "v": "ih",
}

# Default speech rate (chars / second). ElevenLabs at default speed lands
# around this; the schedule still works fine if reality is ±20%.
DEFAULT_CHARS_PER_SEC = 16.0


def build_schedule(text: str, chars_per_sec: float = DEFAULT_CHARS_PER_SEC) -> List[Tuple[float, str]]:
    """Return [(start_time_seconds, viseme_name)] for the given text."""
    if not text or chars_per_sec <= 0:
        return []
    step = 1.0 / chars_per_sec
    schedule: List[Tuple[float, str]] = []
    last: str = ""
    t = 0.0
    for ch in text:
        v = _LETTER_TO_VISEME.get(ch.lower(), _REST)
        if v != last:
            schedule.append((t, v))
            last = v
        t += step
    return schedule


class VisemePlayer:
    """Walks a viseme schedule on a wall clock and blends across boundaries."""

    BLEND_S = 0.06  # crossfade between adjacent visemes for smoothness

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._schedule: List[Tuple[float, str]] = []
        self._t0: float = 0.0
        self._running: bool = False

    def start(self, schedule: List[Tuple[float, str]]) -> None:
        with self._lock:
            self._schedule = list(schedule)
            self._t0 = time.time()
            self._running = bool(schedule)

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._schedule = []

    def current(self) -> Dict[str, float]:
        """Return weights {viseme: 0..1}, summing ~≤1.0 with smooth handoff."""
        out: Dict[str, float] = {v: 0.0 for v in VISEMES}
        with self._lock:
            if not self._running or not self._schedule:
                return out
            t = time.time() - self._t0
            # Find the active and next entry by binary-ish scan.
            sched = self._schedule
            idx = 0
            for i in range(len(sched)):
                if sched[i][0] <= t:
                    idx = i
                else:
                    break
            cur_t, cur_v = sched[idx]
            nxt_t, nxt_v = (sched[idx + 1] if idx + 1 < len(sched) else (cur_t + 0.5, _REST))

        # Crossfade in the last BLEND_S of the current segment.
        seg_left = nxt_t - t
        if cur_v in out:
            out[cur_v] = 1.0
        if seg_left < self.BLEND_S and nxt_v in out and seg_left > 0:
            blend = 1.0 - (seg_left / self.BLEND_S)
            if cur_v in out:
                out[cur_v] = max(0.0, 1.0 - blend)
            out[nxt_v] = max(out.get(nxt_v, 0.0), blend)
        return out


# Module-level singleton — zendaya.py reaches for this so visemes survive
# across `speak_async` calls without juggling instances.
PLAYER = VisemePlayer()


# ───────────────────────────────────────────────────────────────────────────
# Formant-based real-time analyzer
#
# Classifies each PCM window into viseme weights via three spectral bands.
# Much closer to the audio than the char-spread schedule, especially for
# silences (RMS gate → all rest) and elongated vowels.
#
# Bands tuned for human speech (Hz):
#   low:   80–500   — pitch / first-formant region, dominant in oh/ou/aa
#   mid:   500–2000 — second-formant region, dominant in ee/ih
#   high:  2000–5000 — fricatives, sibilants (mostly noise for visemes)
#
# Heuristic mapping (rough, but coherent on streamed TTS):
#   high low/mid ratio, big energy → aa (open jaw)
#   mid > low,  energy moderate    → ee (smile-spread)
#   mid ~ low,  energy moderate    → ih (relaxed wide)
#   low > mid,  energy moderate    → oh (rounded mid)
#   tiny total energy, low-band    → ou (closed/rounded)
# ───────────────────────────────────────────────────────────────────────────


class FormantAnalyzer:
    """PCM window → viseme weights via spectral-band ratios."""

    # Smoothing on the output weights so adjacent frames don't flicker.
    _SMOOTH = 0.55

    def __init__(self, samplerate: int = 22050) -> None:
        self.samplerate = samplerate
        self._prev: Dict[str, float] = {v: 0.0 for v in VISEMES}
        # Cached frequency bin indices, recomputed when window size changes.
        self._bins_for: int = 0
        self._lo_idx = (0, 0)
        self._mid_idx = (0, 0)
        self._hi_idx = (0, 0)

    def reset(self) -> None:
        self._prev = {v: 0.0 for v in VISEMES}

    def _ensure_bins(self, n: int) -> None:
        if n == self._bins_for:
            return
        # FFT bin i corresponds to i * samplerate / n Hz.
        bin_hz = self.samplerate / max(1, n)

        def idx(hz: float) -> int:
            return max(0, min(n // 2, int(round(hz / bin_hz))))

        self._lo_idx = (idx(80), idx(500))
        self._mid_idx = (idx(500), idx(2000))
        self._hi_idx = (idx(2000), idx(5000))
        self._bins_for = n

    def analyze(self, samples_f32, rms: float) -> Dict[str, float]:
        """Return {viseme: 0..1} for the given mono PCM window (float32 -1..1).

        `rms` is already computed by the caller (we get it free from playback).
        Returns all zeros when below a silence threshold.
        """
        import numpy as _np  # local import; module shouldn't force numpy at import

        out = {v: 0.0 for v in VISEMES}
        n = len(samples_f32)
        if n < 32 or rms < 0.012:
            # Silence gate: snap toward rest (decay previous weights too).
            self._prev = {k: v * 0.35 for k, v in self._prev.items()}
            return dict(self._prev)

        self._ensure_bins(n)
        # Real FFT magnitude (window is short → use a Hann to reduce leakage).
        win = _np.hanning(n).astype(_np.float32)
        spec = _np.abs(_np.fft.rfft(samples_f32 * win))
        # Sum energy in each band.
        lo = float(spec[self._lo_idx[0]:self._lo_idx[1]].sum())
        mid = float(spec[self._mid_idx[0]:self._mid_idx[1]].sum())
        hi = float(spec[self._hi_idx[0]:self._hi_idx[1]].sum())
        total = lo + mid + hi + 1e-9
        lo_r = lo / total
        mid_r = mid / total
        hi_r = hi / total

        # Heuristic shape decision. We assign a "primary" plus a smaller
        # secondary so the lerp player still gets smooth transitions.
        primary: str
        secondary: str = ""
        if rms > 0.12 and lo_r > 0.45 and mid_r < 0.40:
            # Big open vowel — split between aa and oh by which dominates.
            primary = "aa" if lo_r < 0.62 else "oh"
            secondary = "oh" if primary == "aa" else "aa"
        elif mid_r > lo_r + 0.05:
            primary = "ee" if mid_r > 0.55 else "ih"
            secondary = "ih" if primary == "ee" else "ee"
        elif lo_r > mid_r + 0.10:
            primary = "oh"
            secondary = "ou" if rms < 0.05 else "aa"
        else:
            # Roughly balanced — relaxed wide.
            primary = "ih"
            secondary = "ee"

        # Energy-scaled weights with one secondary co-fire for blendability.
        amp = min(1.0, rms * 4.0)
        weights = {v: 0.0 for v in VISEMES}
        weights[primary] = amp
        if secondary:
            weights[secondary] = amp * 0.35
        # Sibilants → tilt toward ih so 's/sh' don't look like an open jaw.
        if hi_r > 0.45 and rms < 0.10:
            weights["ih"] = max(weights["ih"], amp * 0.6)
            weights["aa"] *= 0.4
            weights["oh"] *= 0.4

        # Temporal smoothing.
        a = self._SMOOTH
        for k in VISEMES:
            weights[k] = a * self._prev[k] + (1 - a) * weights[k]
        self._prev = weights
        return dict(weights)


# Singleton — initialised lazily by zendaya.py with the actual PCM samplerate.
ANALYZER = FormantAnalyzer()
