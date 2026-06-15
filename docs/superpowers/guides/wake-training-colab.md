# Train your "Zendaya" / "Zen" wake words (free, ~30–60 min)

You don't record your voice and you don't read a script — a free Google Colab
notebook generates thousands of synthetic "Zendaya" clips with AI voices and
trains a small detector on Google's GPU. You just set the word and click Run.

## Steps (do this once per word)

1. Open openWakeWord's automatic training notebook:
   <https://github.com/dscripka/openWakeWord> → README → **"Automatic Model Training (Colab)"**
   (notebook: `notebooks/automatic_model_training.ipynb`). Open it in Colab.
2. In Colab: **Runtime → Change runtime type → GPU → Save**.
3. Find the **`target_word`** cell and set it to:  `Zendaya`
   - Optional quality knobs (recommended): bump `number_of_examples` higher and
     `number_of_training_steps` (more = better, slower).
4. **Runtime → Run all.** It generates positives, downloads negatives, trains,
   and exports an ONNX model. Wait for it to finish (~30–60 min).
5. Download the resulting **`.onnx`** file (Colab's file browser, left panel).
   Rename it to exactly **`zendaya.onnx`**.
6. Repeat steps 3–5 with `target_word = Zen`. **For "Zen" raise the example
   count / steps** (short words need more data) and rename the output to
   **`zen.onnx`**.

## Install the models

Copy both files into:

```
C:\Users\IKA\Zendaya\backend\voice\models\
```

That's it — `WakeEngine` picks them up automatically (no code change). Verify:

```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'backend'); from voice import wake; print(wake._resolve_model_entries())"
```

You should see the two `.onnx` paths. Then run the smoke test:

```powershell
$env:PATH = "C:\Program Files\eSpeak NG;$env:PATH"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -m slow -v
```

Expected: it synthesizes "Zendaya" and confirms the model fires. Finally, start
Zendaya and say **"Zendaya"** once to confirm a live wake.

## Tuning (if needed)

- Too many false wakes (especially "Zen"): raise its threshold —
  `setx ZENDAYA_WAKE_THRESHOLD 0.7` (or edit `_DEFAULT_THRESHOLDS` in `wake.py`).
- Doesn't wake reliably: lower the threshold, or retrain with more examples.
- Use a different model file/location: set `ZENDAYA_WAKE_MODEL` to a
  comma-separated list of `.onnx` paths.
