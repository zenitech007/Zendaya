"""
emotion_engine.py
Advanced Emotion Engine for Zendaya Hologram

This module intelligently computes Zendaya’s emotional state based on:
- System status (CPU, memory, network)
- Time of day and weekday
- Error/health map from services
- Recent amplitude energy (voice stress or loudness)
- Smooth emotion transitions to avoid rapid flicker
"""

import datetime
import psutil
import random
import statistics
import threading
import time


class EmotionState:
    """Tracks Zendaya's evolving emotional state and handles smooth transitions."""
    def __init__(self):
        self.current = "neutral"
        self._lock = threading.Lock()
        self.energy_levels = []  # stores last ~20 amplitude readings
        self._last_update = time.time()

    def _smooth_transition(self, new_emotion: str) -> str:
        """Prevents rapid emotion changes; blends transitions naturally."""
        if new_emotion == self.current:
            return self.current

        now = time.time()
        # Avoid changing too quickly (<2s)
        if now - self._last_update < 2.0:
            return self.current

        self._last_update = now
        self.current = new_emotion
        return self.current

    def update_energy(self, amplitude: float):
        """Tracks recent amplitude (for detecting excitement or stress)."""
        with self._lock:
            self.energy_levels.append(amplitude)
            if len(self.energy_levels) > 20:
                self.energy_levels.pop(0)

    def get_avg_energy(self) -> float:
        """Returns smoothed voice energy level."""
        if not self.energy_levels:
            return 0.0
        return statistics.fmean(self.energy_levels)


emotion_state = EmotionState()


def analyze_system_emotion(status: dict, recent_amp: float | None = None) -> str:
    """
    Determines Zendaya’s emotional tone from system metrics, status map, and recent amplitude.
    Returns one of: calm, focused, energetic, thoughtful, confused, amazed, soothing, alert, playful, neutral
    """

    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # --- System metrics ---
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory().percent
    net_io = psutil.net_io_counters()
    failures = [name for name, ok in status.items() if not ok]

    # --- Amplitude integration ---
    if recent_amp is not None:
        emotion_state.update_energy(recent_amp)
    avg_amp = emotion_state.get_avg_energy()

    # --- Time-based modifiers ---
    if 22 <= hour or hour < 6:
        base_mood = "soothing"
    elif weekday >= 5 and hour < 12:
        base_mood = "playful"
    elif 6 <= hour < 12:
        base_mood = "energetic"
    elif 12 <= hour < 18:
        base_mood = "focused"
    else:
        base_mood = "thoughtful"

    # --- System load influence ---
    if len(failures) >= 3:
        base_mood = "alert"
    elif len(failures) == 2:
        base_mood = "focused"
    elif len(failures) == 1:
        base_mood = "confused"

    # --- CPU & Memory influence ---
    if cpu > 85 or mem > 85:
        base_mood = "stressed"
    elif cpu > 70 or mem > 75:
        base_mood = "focused"

    # --- Audio-driven emotion ---
    if avg_amp > 0.8:
        base_mood = random.choice(["energetic", "amazed", "alert"])
    elif avg_amp > 0.5:
        base_mood = random.choice(["thoughtful", "curious"])
    elif avg_amp < 0.2 and (cpu < 30 and mem < 50):
        base_mood = "calm"

    # --- Random subtle variation (keeps her lifelike) ---
    if random.random() < 0.05:
        base_mood = random.choice(
            ["curious", "amazed", "focused", "playful", "calm", "thoughtful"]
        )

    # --- Apply smooth transition ---
    return emotion_state._smooth_transition(base_mood)


def simulate_emotion_cycle():
    """
    Background emotion updater — useful if you want Zendaya to
    “breathe” emotionally even when idle.
    """
    while True:
        fake_status = {"db": True, "rag": True, "voice": True}
        emotion = analyze_system_emotion(fake_status)
        print(f"[EMOTION] Zendaya feels {emotion}")
        time.sleep(5)


if __name__ == "__main__":
    # Manual test mode
    print("🧠 Emotion engine self-test running...")
    threading.Thread(target=simulate_emotion_cycle, daemon=True).start()
    while True:
        amp = random.random()
        emotion = analyze_system_emotion({"db": True, "rag": True}, recent_amp=amp)
        print(f"Amplitude={amp:.2f} → Emotion={emotion}")
        time.sleep(1.5)
