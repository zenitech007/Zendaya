"""Voice DSP helpers for the v2 listener.

Submodules:
  agc        — automatic gain control (numpy)
  denoise    — DeepFilterNet ONNX wrapper, passthrough fallback
  vad_silero — Silero VAD wrapper with a 30 ms frame API
  wake       — openWakeWord wrapper: smoothing, cooldown, Stage-2 verifier
"""
