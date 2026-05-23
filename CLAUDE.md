# Zendaya — Notes for Claude Code Sessions

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
- After a non-trivial refactor: `graphify update C:\Users\IKA\Zendaya` (AST-only, no LLM tokens).
- After deletions that should shrink the graph: add `--force`.
- For semantic enrichment (one-time, costs Gemini tokens): `graphify extract C:\Users\IKA\Zendaya --backend gemini`.

The `graphify-out/` directory is gitignored — the graph is a regenerable artifact, not source.
