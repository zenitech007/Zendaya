# Zendaya — Notes for Claude Code Sessions

This repo is a **headless Windows desktop voice assistant** (Python, Gemini brain,
offline-first voice). It is **backend-only** — all HUD/pet/Unity/Flutter frontends and the
alternate FastAPI+Supabase backend were removed. The live code is under `backend/`, in
role-based packages:

- `backend/zendaya.py` — main assistant loop (entrypoint; run from the `backend/` cwd by the launcher).
- `backend/zendaya_launcher.py` — process supervisor (spawn / health-check / restart / `--quit`).
- `voice/` — wake word, VAD, denoise, AGC, listeners, visemes, offline TTS.
- `server/` — FastAPI state server (`127.0.0.1:7475`: `/health`, `/chat`, `/quit`, audio/viseme stream) + local music routes.
- `memory/` — JSON facts, vector store, data store.
- `perception/` — webcam, screen, vision, on-screen UI vision, window watcher.
- `skills/` — coder, browser, journal, scheduler, jobs, proactive, alerts, assistant_features (alarms/timers/lists), capabilities, triggers, agent, emotion, languages.
- `integrations/` — google_apis, spotify, home_assistant, phone, github.
- `system/` — system access, installer, hotkeys.

Modules use absolute package imports (e.g. `from memory import data_store`, `import voice.visemes`)
because the assistant runs with `backend/` on `sys.path` (cwd = `backend/`; tests add it via
`backend/tests/conftest.py`). Run tests with:
`venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"`.

The default voice is offline Coqui TTS; switch at runtime with `/voice offline | elevenlabs`.
Offline TTS needs eSpeak-NG installed (`winget install --id eSpeak-NG.eSpeak-NG -e`).

Wake words are custom openWakeWord models (`zendaya.onnx`/`zen.onnx` in
`backend/voice/models/`, trained via `docs/superpowers/guides/wake-training-colab.md`);
the engine falls back to `hey_jarvis` if they're absent. Tune via `ZENDAYA_WAKE_MODEL` /
`ZENDAYA_WAKE_THRESHOLD`.

## Graphify (preferred for codebase questions)

This repo is indexed by [Graphify](https://github.com/safishamsi/graphify). When you need to understand the codebase — how modules relate, where a function is defined, what calls what — prefer the `/graphify` skill over raw `Read`/`Grep`. Graph queries are bounded (default 2000-token budget) and far cheaper than reading whole files.

**One-time setup per PowerShell session (Windows):**

Graphify emits Unicode (emoji, etc.) that crashes the default Windows PowerShell codec. Before invoking `graphify` in a fresh PS session, run:

```powershell
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Skip this and `graphify` calls will throw `UnicodeEncodeError` on output.

**Common queries:**
- `graphify query "<question>"` — semantic BFS over the graph for a question. Returns a list of relevant nodes with file paths + line numbers, capped at the default 2000-token budget.
- `graphify explain "<symbol>"` — structured metadata (NOT prose) for a node: source file, line, community, caller/callee list with edge types. Use it when you need to know what calls what.
- `graphify path "<A>" "<B>"` — shortest path between two nodes. **Works at the function/symbol level, not at the file level.** File nodes are disjoint stars in the AST graph — they have no inter-file edges. If `path "fileA.py" "fileB.py"` returns "no path found", retry with `path "func_in_A" "func_in_B"`.

**When `/graphify` is NOT the right tool:**
- You need to edit a file (use `Read` + `Edit` as normal).
- You need exact byte-level content (use `Read`).
- The graph is stale (last `graphify update` predates a recent refactor). If unsure, run `graphify check-update C:\Users\IKA\Zendaya` first.

**Refreshing the graph:**
> ⚠️ The graph is currently **STALE**: the backend was just reorganized into packages
> (`voice/ server/ memory/ perception/ skills/ integrations/ system/`) and the frontends +
> alternate backend were deleted. Re-run `graphify update C:\Users\IKA\Zendaya --force`
> before relying on it.
- After a non-trivial refactor: `graphify update C:\Users\IKA\Zendaya` (AST-only, no LLM tokens).
- After deletions that should shrink the graph: add `--force`.
- For semantic enrichment (one-time, costs Gemini tokens): `graphify extract C:\Users\IKA\Zendaya --backend gemini`.

The `graphify-out/` directory is gitignored — the graph is a regenerable artifact, not source.
