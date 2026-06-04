# SP-1 · HUD Command Bridge — Design

**Date:** 2026-06-03
**Status:** Approved (design); pending implementation plan
**Part of:** "Full AI UI" initiative (SP-1 of 4)

---

## Context

The Zendaya HUD (`zendaya-hud-react/`, React 18 + TS + Zustand + Three.js)
currently **receives** state from the Python backend over a WebSocket
(`ws://127.0.0.1:7475/ws`) but cannot **send** anything except a keep-alive
ping. The user wants a "full AI UI" where they can drive Zendaya — and change
the HUD — by typing commands directly in the interface.

This is the first of four decomposed sub-projects:

- **SP-1 · Command bridge** *(this spec)* — type commands in the HUD to drive Zendaya + control the HUD.
- **SP-2 · Voice from the HUD** — Zendaya's TTS audio plays in the browser, not the backend.
- **SP-3 · In-HUD music player** — the browser becomes the real music player.
- **SP-4 · Launch & ship** — build-to-static, serve from backend, one-click desktop shortcut, resilience.

Each sub-project gets its own spec → plan → build cycle. SP-1 is foundational:
once the HUD can *send*, later features can be driven by command.

### What already exists (verified)

- **Backend command endpoint:** the state server (`backend/zendaya_state_server.py`)
  already exposes `POST /chat` → `handle_user_command()` on a worker thread.
  The HUD only needs to *send* to it.
- **WS `/ws`:** broadcast-only today; it receives inbound text but ignores it
  (a "accept JSON commands later" placeholder). SP-1 does **not** use this path.
- **`terminalOpen` store flag:** exists in `zendayaStore`, toggled by the WS
  actions `show_terminal` / `hide_terminal`, but **nothing renders an input** —
  it is a latent flag. SP-1 gives it a real UI.
- **WS action vocabulary:** `useWebSocket.ts`'s `dispatchAction` already maps
  named actions (`open_map`, `set_theme`, `open_module`, `dock_orb`,
  `minimize_ui`, `activate_voice`, …) to store setters.

## Goals

1. A summoned, themed terminal overlay in the HUD with a command input and a
   compact in-session transcript.
2. **Hybrid command model:** natural-language lines go to Zendaya's brain via
   `POST /chat`; leading-`/` lines are instant client-side HUD controls.
3. Zendaya's reply (already broadcast as `text`) echoes into the transcript.
4. **Zero backend changes.** No edits to any Python file.

## Non-goals (deferred, not dropped)

- WS-inbound JSON command protocol (the `/ws` placeholder) — SP-1 needs only
  `POST /chat` + client-side slash handling.
- Command history (↑/↓ recall), autocomplete, persisting the transcript across
  reloads.
- Any SP-2/3/4 feature (voice-from-HUD, music playback, launcher).

## Architecture

All new code under `zendaya-hud-react/src/`. The design favors small, pure,
independently testable units; React/DOM glue is thin and smoke-tested.

```
 user types ──▶ CommandTerminal.onSubmit
                     │
                     ├─ parseCommand(input)
                     │      ├─ {kind:"slash", name, args} ──▶ slashRegistry.run ──▶ hudControls ──▶ store setters
                     │      │                                                   └─ returns result string ─▶ system line
                     │      └─ {kind:"chat", text} ──▶ api/backend.sendChat ──▶ POST /chat
                     │                                                              └─ await reply
                     └─ pushTerminalLine(user line)

 backend ──WS──▶ store.text updates ──▶ CommandTerminal effect (while awaiting) ──▶ pushTerminalLine(zendaya line)
```

### Components & responsibilities

**New files**

| File | Responsibility | Depends on |
|---|---|---|
| `src/commands/parseCommand.ts` | Pure: `parseCommand(input)` → slash or chat descriptor. No React, no store. | — |
| `src/commands/hudControls.ts` | The HUD-mutation functions (`openModule`, `closeModule`, `setThemeById`, `openMap`, `goHome`, `dock`, `undock`, `minimize`, `restore`, `setVoice`). Single source of truth for both the slash layer and the WS handler. | `zendayaStore` |
| `src/commands/slashRegistry.ts` | Pure map `name → { run(args): string, help }`; `run` calls `hudControls`, returns a transcript message. | `hudControls` |
| `src/api/backend.ts` | `sendChat(text): Promise<void>` — POSTs `/chat`; derives http origin from the WS URL origin (`127.0.0.1:7475`). | `fetch` |
| `src/components/HUD/CommandTerminal.tsx` | The summoned themed console overlay: transcript + input; submit handling; reply echo; Esc to close. Bound to `terminalOpen`. | store, parseCommand, slashRegistry, backend |
| `src/hooks/useCommandHotkey.ts` | Global key listener: Ctrl+K toggles `terminalOpen`; Esc closes. | store |

**Modified files**

| File | Change |
|---|---|
| `src/store/zendayaStore.ts` | Add in-memory `terminalLog: TerminalLine[]` + `pushTerminalLine(line)` + `clearTerminalLog()`. **Not** persisted to localStorage (fresh each session). |
| `src/hooks/useWebSocket.ts` | Refactor `dispatchAction` cases to call `hudControls` (behavior identical; removes duplication). |
| `src/App.tsx` | Mount `<CommandTerminal />`. |
| `src/index.css` | `.zen-terminal*` classes using `var(--zen-*)` tokens only. |

### Types

```ts
// parseCommand.ts
export type ParsedCommand =
  | { kind: "slash"; name: string; args: string[] }
  | { kind: "chat"; text: string };

// store
export type TerminalRole = "user" | "zendaya" | "system";
export interface TerminalLine { id: string; role: TerminalRole; text: string; ts: number; }
```

## Data flow (one submit)

1. Terminal summoned via Ctrl+K, the chrome button, or Zendaya's `show_terminal`
   WS action → `terminalOpen=true` → overlay renders, input auto-focused.
2. User types + Enter → push the user line to `terminalLog`, then `parseCommand`:
   - **slash** → `slashRegistry.run(name, args)` mutates the store via
     `hudControls` instantly; push the returned system line (`→ theme set to iris`).
   - **chat** → `sendChat(text)` POSTs `/chat`; mark "awaiting reply."
3. Zendaya replies through the **unchanged** backend path — broadcast `state`/`text`
   over WS → store `text` updates. While awaiting, the overlay's effect pushes a
   `zendaya` line and clears the awaiting flag. Her voice + orb reaction are untouched.
4. Esc / `hide_terminal` → `terminalOpen=false`; transcript retained in the store
   for the next open.

## Initial slash command set

All reuse `hudControls`. Case-insensitive command names.

| Command | Effect |
|---|---|
| `/theme <forge\|iris>` | `setThemeById` (validates id) |
| `/map` | open map scene (scene=map, module=map, panel=globe) |
| `/weather` | open weather module |
| `/clock` | open clock module |
| `/home` | back to idle (scene=main, module=none, panel=none) |
| `/dock`, `/undock` | `setDocked(true/false)` |
| `/minimize`, `/restore` | `setMinimized(true/false)` |
| `/voice <on\|off>` | `setVoiceActive(true/false)` |
| `/help` | list commands into the transcript |
| (unknown) | `unknown command: /xyz (try /help)` |
| `/` alone | treated as `/help` |

## Error handling

- **Backend unreachable / POST fails** → catch → system line
  `⚠ can't reach Zendaya (is the backend running?)`. The store's `connected`
  flag also visibly disables the send affordance when the WS is down.
- **Bad slash arg** (`/theme banana`) → registry validates against known ids →
  `unknown theme: banana`.
- **Empty input** → no-op.
- **No reply** (her `text` never changes after a chat) → no echo; nothing hangs
  (the awaiting flag clears on the next submit).

## Testing strategy

happy-dom has no WebGL/Web Audio and does not exercise real network — so pure
logic is unit-tested and DOM/network glue is smoke-tested live (the Phase B/C
pattern: drive the real Zustand singleton through Vite's dev module graph).

**Unit (vitest / happy-dom):**
- `parseCommand` — slash vs chat, arg splitting, leading/trailing whitespace,
  empty string, lone `/`, multi-space args.
- `slashRegistry` + `hudControls` — run each command against a fresh store
  instance; assert theme / scene / module / dock / minimize / voice mutations;
  assert unknown-command and bad-arg messages.
- `backend.sendChat` — mock `fetch`; assert method, URL (`http://127.0.0.1:7475/chat`),
  JSON body `{message}`, and that a non-ok response / network error rejects.

**Light DOM test (RTL):**
- `CommandTerminal` renders the input when `terminalOpen=true`, renders nothing
  (or hidden) when false, and renders transcript lines from the store.

**Live smoke (manual, against a running backend):**
- Ctrl+K toggles the terminal; `show_terminal`/`hide_terminal` from the store
  toggle it too.
- `/theme iris` flips the theme instantly with no network.
- A natural-language line round-trips: user line appears, Zendaya's reply echoes,
  and she still speaks/reacts via the existing backend path.

## Done criteria

1. Typing a natural-language line in the HUD reaches Zendaya and her reply echoes
   into the transcript; she still speaks via the existing path.
2. `/`-prefixed commands change the HUD instantly with no backend round-trip.
3. The terminal opens/closes via hotkey, Esc, the chrome button, and Zendaya's
   existing `show_terminal`/`hide_terminal` voice actions.
4. `dispatchAction` and the slash layer share `hudControls` (no duplicated
   mutation logic).
5. All new pure logic is unit-tested and green; build (`tsc --noEmit && vite build`)
   is clean; no Python file is modified.

## Safety constraints (carried from the project's standing rules)

- All work under `zendaya-hud-react/src/` (+ this `docs/` spec). No edits to
  `backend/`, Python, `pyproject.toml`, `.gitignore`, or other config.
- Never disturb the pre-existing uncommitted working-tree diff; never `git add -A`/`.`/`-u`.
  Stage only the exact files named in each task's commit step.
- All commits disable signing (`git -c commit.gpgsign=false`). After each commit,
  `git status` to confirm no protected paths were swept in. Never stage anything
  under `.claude/` or `.superpowers/`.
