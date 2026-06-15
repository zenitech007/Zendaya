"""Voice I/O: speech-in (wake word, VAD, denoise, AGC, listeners) and
speech-out (visemes, offline TTS).

Submodules:
  wake        — openWakeWord wrapper: smoothing, cooldown, Stage-2 verifier
  vad_silero  — Silero VAD wrapper with a 30 ms frame API
  denoise     — DeepFilterNet ONNX wrapper, passthrough fallback
  agc         — automatic gain control (numpy)
  listener    — primary mic listener
  listener_v2 — upgraded listener (denoise + VAD + async dispatch worker)
  visemes     — formant-based mouth-shape weights for lip-sync
  offline_tts — Coqui VITS offline text-to-speech
"""
