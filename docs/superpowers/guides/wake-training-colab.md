# Train your "Zendaya" / "Zen" wake words (free, ~30–90 min)

You don't record your voice and you don't read a script — a free Google Colab
notebook generates thousands of synthetic "Zendaya" clips with AI voices and
trains a small detector on Google's GPU. You just set the word and click Run.

> Use the **fixed notebook in this repo**:
> [`docs/superpowers/guides/automatic_model_training.ipynb`](automatic_model_training.ipynb).
> It's the upstream openWakeWord auto-trainer with the dependency / dataset / config
> bugs already patched for current Colab (the stock notebook from GitHub no longer
> installs — old TensorFlow pins, a dead AudioSet download, numpy 2 conflicts). Don't
> grab the one from the openWakeWord README.

## Steps (do this once per word)

1. Open Colab (<https://colab.research.google.com>) → **File → Upload notebook** and
   upload `docs/superpowers/guides/automatic_model_training.ipynb` from this repo.
2. **Runtime → Change runtime type → GPU → Save.**
3. In the config cell (titled *WAKE-WORD CONFIG*) leave the one parameter as:
   ```python
   WAKE_PHRASE = "zendaya"
   ```
   (lowercase — the output filename and the runtime threshold are keyed on it).
   The training sizes are already set to non-toy values (`n_samples=20000`,
   `steps=50000`); raise them for an even stronger model (more = better, slower).
4. **Runtime → Run all.** It installs deps, downloads negatives, generates positives,
   augments, trains, and exports an ONNX model. Wait for it to finish (~30–90 min;
   free GPUs aren't guaranteed and a real run can take longer).
   - If a cell throws a `numpy`/`pyarrow` ABI error, do **Runtime → Restart session**,
     re-run the **Environment Setup** cell, then continue (the notebook has a callout
     explaining this — it's Colab silently reverting numpy to 2.x).
5. Download **`my_custom_model/zendaya.onnx`** from Colab's file browser (left panel).
   It's already named correctly — just confirm the name is exactly `zendaya.onnx`
   (all lowercase, no trailing space/underscore).
6. Repeat with `WAKE_PHRASE = "zen"`. **For "Zen" also uncomment the `(zen)` block**
   in the config cell (more samples + confuser phrases — short words need more data).
   Download `my_custom_model/zen.onnx`.

> tflite is **not** needed — Zendaya loads `.onnx` only. The optional Step 4 cell is
> off by default; leave it off.

## Install the models

Copy both files into:

```
C:\Users\IKA\Zendaya\backend\voice\models\
```

That's it — `WakeEngine` picks them up automatically (no code change). Verify the
real on-disk names are exactly `zendaya.onnx` / `zen.onnx`:

```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import glob, os; [print(repr(os.path.basename(p))) for p in glob.glob(r'backend\voice\models\*.onnx')]"
```

Then confirm the engine resolves them:

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

- Too many false wakes (especially "Zen"): raise its threshold. Prefer the per-model
  default in `_DEFAULT_THRESHOLDS` in `backend/voice/wake.py` (`zen` is already `0.7`)
  over `setx ZENDAYA_WAKE_THRESHOLD 0.7`, which applies to **every** model and would
  also blunt `zendaya`'s recall.
- Doesn't wake reliably: lower the threshold, or retrain with more examples / steps.
- Use a different model file/location: set `ZENDAYA_WAKE_MODEL` to a
  comma-separated list of `.onnx` paths.
