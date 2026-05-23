# Graphify Setup for Zendaya — Design

**Date:** 2026-05-23
**Status:** Approved (pending spec review)
**Author:** Claude Opus 4.7 (with zenitech007)

## Goal

Make `C:\Users\IKA\Zendaya` queryable via Graphify so future Claude Code sessions use compact graph queries (default 2000-token budget) instead of reading raw files. Lower the user's token cost on Claude Code sessions targeting this repo. **No runtime change to the Zendaya assistant itself.**

## Non-goals

- Integrating Graphify *into* the Zendaya assistant runtime (the Gemini-driven `backend/zendaya.py`).
- Replacing or modifying the existing memory stack (`zendaya_vector_memory.py`, `zendaya_memory_facts.py`).
- Cross-repo / global graph.
- Live file-watching.
- Semantic LLM-driven extraction (deferred — AST-only first).

## Context

Graphify (`graphifyy` 0.8.5, PyPI; CLI `graphify`) is installed at `C:\Users\IKA\.local\bin\graphify.exe` via pipx (venv at `C:\Users\IKA\pipx\venvs\graphifyy`). It indexes a code folder into a knowledge graph (`graph.json`) using tree-sitter for AST extraction, and exposes a Claude Code skill so future sessions can query the graph via `/graphify`.

Current Zendaya repo state at design time:
- ~32 untracked Python modules in `backend/` (large uncommitted build-out).
- 3 untracked frontends (`zendaya-hud-react/`, `zendaya-hud-template/`, `zendaya-pet/`).
- 4,400+ line uncommitted diff. User has explicitly opted to leave it alone for now.

Graphify's built-in `_SKIP_DIRS` (in `graphify/detect.py:365`) covers: `venv`, `.venv`, `env`, `.env`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `target`, `out`, `site-packages`, `lib64`. No env-var hook exists for additional excludes; tree-sitter only processes code files, so binary/data dirs (e.g. `webview2-runtime/`, `zendaya_logs/chroma/`) are skipped naturally.

## Architecture

One CLI tool. No daemon, no service. Three artifacts:

| Artifact | Location | Purpose | Tracked in git? |
|---|---|---|---|
| Claude Code skill | `C:\Users\IKA\.claude\skills\graphify\` | Makes `/graphify` discoverable | N/A (user-global) |
| Knowledge graph | `C:\Users\IKA\Zendaya\graphify-out\graph.json` | The queryable index | No (regenerable; ignored) |
| Optional viz | `C:\Users\IKA\Zendaya\graphify-out\GRAPH_TREE.html` | Human-browsable tree | No |

## Sequence

1. **Register the Claude Code skill** — `graphify install --platform claude`
   Verify: `Get-ChildItem $env:USERPROFILE\.claude\skills\graphify -Recurse | Select-Object -First 5`

2. **AST-only initial build** — `graphify update C:\Users\IKA\Zendaya`
   - Uses tree-sitter; no LLM tokens spent.
   - Built-in `_SKIP_DIRS` handles `node_modules`, `target`, `.venv`, `.git`, `dist`, `build`, `__pycache__`, `site-packages`.
   - Verify: `graphify-out\graph.json` exists and is > 50 KB.

3. **Smoke-test queries** — confirm the graph answers real codebase questions:
   - `graphify query "How does zendaya.py assemble the LLM prompt?"`
   - `graphify explain "gemini_reply"`
   - `graphify path "zendaya.py" "zendaya_vector_memory.py"`

4. **Add `graphify-out/` to `.gitignore`** — regenerable artifact, must not be committed.

5. **Document workflow in `CLAUDE.md`** — add a short section telling future Claude Code sessions to prefer `/graphify query` over raw `Read` calls for codebase questions.

## Done criteria

- `graphify install --platform claude` succeeds; skill files present under `~/.claude/skills/graphify/`.
- `graphify update` produces a non-empty `graph.json` (> 50 KB).
- All three smoke-test queries return graph-cited answers (not "no results").
- `graphify-out/` line present in `.gitignore`.
- A `## Graphify` (or equivalent) section in `CLAUDE.md` tells future sessions when and how to use `/graphify`.

## Risks and unknowns

| Risk | Mitigation |
|---|---|
| `graphify update` picks up `zendaya_logs/journal/*.json` or `zendaya_data/*.json` as data files and bloats the graph | AST extractor likely ignores non-code; if graph.json > 5 MB or graph queries are noisy, revisit and ask upstream about extra excludes |
| AST-only graph is too shallow for cross-module reasoning | Escape hatch: run `graphify extract C:\Users\IKA\Zendaya --backend gemini` for semantic enrichment (costs Gemini tokens, one-time) |
| Python 3.14.3 too new for a tree-sitter binding | If a binding fails on first run, fall back to running graphify against a 3.12 venv |
| Skill installation in `~/.claude/skills/graphify/` conflicts with a future plugin | Low risk — directory does not currently exist; if it later collides, `graphify uninstall` reverses cleanly |

## Deferred / future work

- **Semantic LLM extraction** (`graphify extract --backend gemini`) — only if AST-only graph proves too thin in real use.
- **Live watch** (`graphify watch`) — disk churn; manual `graphify update` after refactors is enough for now.
- **Other AI platforms** (`--platform cursor|gemini|codex|aider`) — add when the user adopts them.
- **Global cross-repo graph** (`graphify global add`) — single-repo for now.
- **The follow-up "wire up an untracked module" task** — separate spec; do it after Graphify is verified working.
