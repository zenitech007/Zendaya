# Graphify Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install Graphify's Claude Code skill, build an AST knowledge graph of the Zendaya repo, and document its use so future Claude Code sessions query the graph instead of reading raw files.

**Architecture:** Single CLI tool (`graphify` 0.8.5, installed via pipx). Outputs a `graph.json` under `graphify-out/`. The `graphify install --platform claude` command provisions the `/graphify` skill at `~/.claude/skills/graphify/`. No runtime change to the Zendaya assistant.

**Tech Stack:** Graphify (Python, tree-sitter under the hood), PowerShell 5.1 (Windows shell), Git for two small commits.

**Spec:** [docs/superpowers/specs/2026-05-23-graphify-setup-design.md](../specs/2026-05-23-graphify-setup-design.md)

---

## File Structure

| File / Path | Action | Purpose |
|---|---|---|
| `C:\Users\IKA\.claude\skills\graphify\` | Created externally by `graphify install` | Makes `/graphify` discoverable in future Claude Code sessions |
| `C:\Users\IKA\Zendaya\.gitignore` | Modify (append one line) | Exclude regenerable `graphify-out/` |
| `C:\Users\IKA\Zendaya\graphify-out\graph.json` | Created externally by `graphify update` | The knowledge graph artifact (not committed) |
| `C:\Users\IKA\Zendaya\CLAUDE.md` | Create | Tells future Claude Code sessions when and how to use `/graphify` |

---

## Conventions for this plan

- Shell is **PowerShell 5.1** on Windows. Commands use PS syntax (`$null`, `Test-Path`, `Get-Content`, etc.). No `&&` — use `;` or `if ($?) { ... }`.
- "Verification" replaces TDD "tests" — this is CLI orchestration plus two text edits, not a code project. Each task ends with a concrete `Expected:` check.
- All commands run from the repo root unless noted: `C:\Users\IKA\Zendaya`.
- `graphify` is on PATH at `C:\Users\IKA\.local\bin\graphify.exe` (verified at design time).

---

### Task 1: Register the Graphify skill for Claude Code

**Files:**
- Create: `C:\Users\IKA\.claude\skills\graphify\` (directory + skill files, written by `graphify install`)

- [ ] **Step 1: Run the install command**

```powershell
graphify install --platform claude
```

Expected output: a message like `installed graphify skill to ...` (exact wording depends on graphify version). Exit code 0.

- [ ] **Step 2: Verify the skill directory was created**

```powershell
Test-Path "$env:USERPROFILE\.claude\skills\graphify"
Get-ChildItem "$env:USERPROFILE\.claude\skills\graphify" -Recurse | Select-Object -First 10 Name, Length
```

Expected: first command prints `True`; second lists at least one file (e.g. `SKILL.md` or similar). If the directory is empty, treat as failure and inspect `graphify install --help` for additional flags.

- [ ] **Step 3: No commit**

This is a user-global change at `~/.claude/skills/`. It is not part of this repo.

---

### Task 2: Add `graphify-out/` to `.gitignore`

**Files:**
- Modify: `C:\Users\IKA\Zendaya\.gitignore` (append one section near the end)

- [ ] **Step 1: Verify the entry is not already present**

```powershell
Select-String -Path .gitignore -Pattern "graphify-out" -SimpleMatch
```

Expected: no output (no existing match). If a match exists, skip to Step 4.

- [ ] **Step 2: Append the ignore rule**

Use the `Edit` tool to add the following block at the end of `.gitignore` (after the last existing line, line 424):

```
# Graphify knowledge graph (regenerable)
graphify-out/
```

- [ ] **Step 3: Verify the rule is in place**

```powershell
Select-String -Path .gitignore -Pattern "graphify-out" -SimpleMatch
```

Expected: one matching line containing `graphify-out/`.

- [ ] **Step 4: Commit**

```powershell
git add .gitignore
git -c commit.gpgsign=false commit -m "chore: ignore graphify-out/ knowledge graph artifacts"
```

Expected: commit succeeds; `git status --short .gitignore` returns empty.

---

### Task 3: Build the AST knowledge graph

**Files:**
- Create: `C:\Users\IKA\Zendaya\graphify-out\graph.json` (written by `graphify update`)

- [ ] **Step 1: Run AST-only graph build**

```powershell
graphify update C:\Users\IKA\Zendaya
```

Expected: progress output mentioning files extracted; final summary line with node/edge counts; exit code 0. May take 30s–3 min depending on repo size.

Note: this is AST-only — no LLM tokens spent. Built-in `_SKIP_DIRS` handles `node_modules`, `target`, `.venv`, `.git`, `dist`, `build`, `__pycache__`, `site-packages`.

- [ ] **Step 2: Verify graph.json exists and is non-trivial**

```powershell
$g = "C:\Users\IKA\Zendaya\graphify-out\graph.json"
if (Test-Path $g) { $size = (Get-Item $g).Length; "graph.json size: $size bytes"; if ($size -gt 51200) { "PASS: > 50 KB" } else { "FAIL: too small" } } else { "FAIL: graph.json missing" }
```

Expected: output ends with `PASS: > 50 KB`. If too small, the extractor likely failed on Python 3.14 — fall back to running graphify against a Python 3.12 venv (see spec risks section).

- [ ] **Step 3: Verify graph.json is ignored by git**

```powershell
git status --short graphify-out/ 2>&1
git check-ignore -v graphify-out/graph.json
```

Expected: first command prints nothing (clean); second confirms the ignore rule from `.gitignore` matches.

- [ ] **Step 4: No commit**

The artifact is gitignored; nothing to commit for this task.

---

### Task 4: Smoke-test queries against the graph

**Files:** None (read-only against `graphify-out/graph.json`).

- [ ] **Step 1: Query — prompt assembly**

```powershell
graphify query "How does zendaya.py assemble the LLM prompt?"
```

Expected: output mentions `gemini_reply` or `zendaya.py` and cites graph nodes. Should NOT print "no results" or empty output. Token usage shown at end should be under 2000 (default budget).

- [ ] **Step 2: Query — explain a known function**

```powershell
graphify explain "gemini_reply"
```

Expected: a plain-language explanation of the `gemini_reply` function plus a list of neighboring nodes (callers, callees, files). If output is "node not found", the graph did not extract this function — investigate before proceeding.

- [ ] **Step 3: Query — path between two files**

```powershell
graphify path "zendaya.py" "zendaya_vector_memory.py"
```

Expected: a chain of nodes/edges connecting the two files. Confirms the graph captures inter-module relationships (one of the main benefits over raw file reads).

- [ ] **Step 4: Record any failures inline**

If any of Steps 1–3 returned "no results" or "node not found", do NOT proceed to Task 5. Instead:
- Re-read the graph build output from Task 3 for warnings.
- Try `graphify update C:\Users\IKA\Zendaya --force` to rebuild.
- If still failing, document the failure in this plan as a checkbox-noted blocker and report back.

- [ ] **Step 5: No commit**

Queries are read-only.

---

### Task 5: Document the workflow in `CLAUDE.md`

**Files:**
- Create: `C:\Users\IKA\Zendaya\CLAUDE.md`

- [ ] **Step 1: Verify CLAUDE.md does not already exist**

```powershell
Test-Path C:\Users\IKA\Zendaya\CLAUDE.md
```

Expected: `False`. If `True`, read the existing file and add the Graphify section to it instead of overwriting.

- [ ] **Step 2: Create CLAUDE.md with the Graphify section**

Use the `Write` tool to create `CLAUDE.md` with this exact content:

```markdown
# Zendaya — Notes for Claude Code Sessions

## Graphify (preferred for codebase questions)

This repo is indexed by [Graphify](https://github.com/safishamsi/graphify). When you need to understand the codebase — how modules relate, where a function is defined, what calls what — prefer the `/graphify` skill over raw `Read`/`Grep`. Graph queries are bounded (default 2000-token budget) and far cheaper than reading whole files.

**Common queries:**
- `graphify query "<question>"` — semantic BFS over the graph for a question
- `graphify explain "<symbol>"` — plain-language explanation of a node and its neighbors
- `graphify path "<A>" "<B>"` — shortest path between two nodes (file paths or symbol names)

**When `/graphify` is NOT the right tool:**
- You need to edit a file (use `Read` + `Edit` as normal).
- You need exact byte-level content (use `Read`).
- The graph is stale (last `graphify update` predates a recent refactor). If unsure, run `graphify check-update C:\Users\IKA\Zendaya` first.

**Refreshing the graph:**
- After a non-trivial refactor: `graphify update C:\Users\IKA\Zendaya` (AST-only, no LLM tokens).
- After deletions that should shrink the graph: add `--force`.
- For semantic enrichment (one-time, costs Gemini tokens): `graphify extract C:\Users\IKA\Zendaya --backend gemini`.

The `graphify-out/` directory is gitignored — the graph is a regenerable artifact, not source.
```

- [ ] **Step 3: Verify the file exists and contains the section heading**

```powershell
Test-Path C:\Users\IKA\Zendaya\CLAUDE.md
Select-String -Path CLAUDE.md -Pattern "^## Graphify" -SimpleMatch
```

Expected: first command prints `True`; second prints one matching line.

- [ ] **Step 4: Commit**

```powershell
git add CLAUDE.md
git -c commit.gpgsign=false commit -m "docs: add CLAUDE.md with Graphify usage guidance"
```

Expected: commit succeeds; `git status --short CLAUDE.md` returns empty.

---

### Task 6: Final verification against spec done criteria

**Files:** None (read-only verification).

- [ ] **Step 1: Check each spec done-criterion explicitly**

Run this verification block and confirm every line ends with PASS:

```powershell
$pass = @()
$fail = @()

# 1. Skill installed
if (Test-Path "$env:USERPROFILE\.claude\skills\graphify") { $pass += "skill dir present" } else { $fail += "skill dir MISSING" }

# 2. graph.json > 50 KB
$g = "C:\Users\IKA\Zendaya\graphify-out\graph.json"
if ((Test-Path $g) -and ((Get-Item $g).Length -gt 51200)) { $pass += "graph.json > 50KB" } else { $fail += "graph.json missing or small" }

# 3. .gitignore contains graphify-out
if (Select-String -Path C:\Users\IKA\Zendaya\.gitignore -Pattern "graphify-out" -SimpleMatch -Quiet) { $pass += "gitignore rule present" } else { $fail += "gitignore rule MISSING" }

# 4. CLAUDE.md present and has Graphify section
if ((Test-Path C:\Users\IKA\Zendaya\CLAUDE.md) -and (Select-String -Path C:\Users\IKA\Zendaya\CLAUDE.md -Pattern "^## Graphify" -SimpleMatch -Quiet)) { $pass += "CLAUDE.md Graphify section present" } else { $fail += "CLAUDE.md or section MISSING" }

"PASS:"; $pass | ForEach-Object { "  - $_" }
""
"FAIL:"; $fail | ForEach-Object { "  - $_" }
if ($fail.Count -eq 0) { ""; "ALL DONE-CRITERIA MET" } else { ""; "BLOCKERS REMAIN" }
```

Expected: every check listed under `PASS:`, none under `FAIL:`, final line `ALL DONE-CRITERIA MET`.

- [ ] **Step 2: Confirm smoke-test queries from Task 4 returned real results**

Re-read your notes from Task 4. If any of the three queries returned "no results" or failed, the implementation is NOT complete despite Step 1 passing — flag it.

- [ ] **Step 3: Summarize the result**

Output a single short status line for the user, e.g.:
- `Graphify setup complete. Skill installed, graph built (N nodes), 3 smoke tests passed, CLAUDE.md committed.`
- Or, if any blocker: `Graphify setup blocked: <one-line reason>. See plan for details.`

No commit. End of plan.

---

## Out of scope (for follow-up plans)

- Wiring up one of the untracked backend modules (the next task the user asked for; separate spec needed).
- Semantic LLM extraction (`graphify extract --backend gemini`) — defer until AST-only graph proves too thin.
- `graphify watch` for live updates.
- Installing the skill on Cursor / Gemini CLI / other platforms.
- Touching the 4,400-line uncommitted diff — user has explicitly opted to leave it alone.
