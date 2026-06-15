# Wake-word models

Drop the trained openWakeWord models here:

- `zendaya.onnx`  — primary wake word
- `zen.onnx`      — secondary wake word

`WakeEngine` loads these automatically (see `_resolve_model_entries` in
`../wake.py`). If they're absent it falls back to the built-in `hey_jarvis`
model, so the assistant still wakes during the interim.

Train them with the free Colab guide:
`docs/superpowers/guides/wake-training-colab.md`. Override the path(s) at runtime
with `ZENDAYA_WAKE_MODEL` (comma-separated) and tune with `ZENDAYA_WAKE_THRESHOLD`.
