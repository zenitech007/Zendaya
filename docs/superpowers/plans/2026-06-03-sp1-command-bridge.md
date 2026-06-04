# SP-1 · HUD Command Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the HUD a summoned terminal overlay where typed natural-language lines go to Zendaya (`POST /chat`) and leading-`/` lines instantly control the HUD client-side.

**Architecture:** A pure parser (`parseCommand`) splits input into slash vs chat. Slash commands run through a registry that calls a shared `hudControls` module (the single source of truth for HUD mutations, also adopted by the existing WS `dispatchAction`). Chat lines POST to the backend's existing `/chat` endpoint; Zendaya's reply echoes into an in-store transcript. Zero backend edits.

**Tech Stack:** React 18 + TypeScript, Zustand 4, Vite 5, Vitest 2 + happy-dom, @testing-library/react.

**Design spec:** `docs/superpowers/specs/2026-06-03-sp1-command-bridge-design.md`

---

## Conventions for every task

- **Repo root:** `C:/Users/IKA/Zendaya`. All app code is under `zendaya-hud-react/`.
- **Run a single test file:** `npm --prefix zendaya-hud-react run test -- <fileName>`
- **Run the whole suite:** `npm --prefix zendaya-hud-react run test`
- **Build (typecheck + bundle):** `npm --prefix zendaya-hud-react run build`
- **Tests** live in `zendaya-hud-react/src/__tests__/*.test.ts(x)`, use `vitest` (`describe/it/expect`), reset store state with `useZendaya.setState({...})` in `beforeEach`, and read it with `useZendaya.getState()`. Component tests use `@testing-library/react` (`render`, `screen`, `fireEvent`) — see existing `src/__tests__/ChromeFrame.test.tsx`, `ThemePicker.test.tsx`.

### SAFETY CONSTRAINTS (mandatory, every commit)

- Only touch files under `zendaya-hud-react/src/` (+ this plan's `docs/`). **No** edits to `backend/`, any `.py`, `pyproject.toml`, `.gitignore`, or other config.
- There is a large pre-existing uncommitted working-tree diff (in `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`) that must **never** be staged, reverted, or disturbed.
- **Never** `git add -A`, `git add .`, or `git add -u`. Stage only the exact files named in the task's commit step.
- All commits disable signing: `git -c commit.gpgsign=false commit ...`.
- After every commit, run `git status` and confirm no protected path was swept in.
- Never stage anything under `.claude/` or `.superpowers/`.
- CRLF warnings from Git on Windows are expected — ignore them.

---

## File Structure

**New files**

| File | Responsibility |
|---|---|
| `zendaya-hud-react/src/commands/parseCommand.ts` | Pure: input string → `{kind:"slash",name,args}` / `{kind:"chat",text}` / `null`. |
| `zendaya-hud-react/src/commands/hudControls.ts` | Shared HUD-mutation functions over the store singleton. Single source of truth for slash + WS. |
| `zendaya-hud-react/src/commands/slashRegistry.ts` | `SLASH_COMMANDS` map + `runSlash(name,args)` → transcript message string. |
| `zendaya-hud-react/src/api/backend.ts` | `backendHttpOrigin()` + `sendChat(text)` (POST `/chat`). |
| `zendaya-hud-react/src/hooks/useCommandHotkey.ts` | Global keydown: Ctrl/Cmd+K toggles terminal, Esc closes. |
| `zendaya-hud-react/src/components/HUD/CommandTerminal.tsx` | The summoned console overlay (transcript + input + submit + reply echo). |

**Modified files**

| File | Change |
|---|---|
| `zendaya-hud-react/src/store/zendayaStore.ts` | Add `TerminalRole`/`TerminalLine` types, `terminalLog` state, `pushTerminalLine`, `clearTerminalLog`. |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` | Export `dispatchAction`; refactor its body to call `hudControls`. |
| `zendaya-hud-react/src/App.tsx` | Mount `<CommandTerminal />`. |
| `zendaya-hud-react/src/index.css` | Append `.zen-terminal*` classes (theme tokens only). |

**New test files**

`parseCommand.test.ts`, `hudControls.test.ts`, `slashRegistry.test.ts`, `backend.test.ts`, `terminalLog.test.ts`, `dispatchAction.test.ts`, `useCommandHotkey.test.tsx`, `CommandTerminal.test.tsx` — all under `zendaya-hud-react/src/__tests__/`.

---

## Task 1: parseCommand (pure parser)

**Files:**
- Create: `zendaya-hud-react/src/commands/parseCommand.ts`
- Test: `zendaya-hud-react/src/__tests__/parseCommand.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/parseCommand.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { parseCommand } from "../commands/parseCommand";

describe("parseCommand", () => {
  it("returns null for empty / whitespace input", () => {
    expect(parseCommand("")).toBeNull();
    expect(parseCommand("   ")).toBeNull();
  });
  it("parses a chat line", () => {
    expect(parseCommand("  what time is it?  ")).toEqual({ kind: "chat", text: "what time is it?" });
  });
  it("parses a slash command with no args", () => {
    expect(parseCommand("/map")).toEqual({ kind: "slash", name: "map", args: [] });
  });
  it("lowercases the command name and keeps arg case", () => {
    expect(parseCommand("/Theme Iris")).toEqual({ kind: "slash", name: "theme", args: ["Iris"] });
  });
  it("splits multiple args on runs of whitespace", () => {
    expect(parseCommand("/foo  a   b")).toEqual({ kind: "slash", name: "foo", args: ["a", "b"] });
  });
  it("treats a lone slash as /help", () => {
    expect(parseCommand("/")).toEqual({ kind: "slash", name: "help", args: [] });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- parseCommand`
Expected: FAIL — cannot find module `../commands/parseCommand`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/commands/parseCommand.ts`:

```ts
export type ParsedCommand =
  | { kind: "slash"; name: string; args: string[] }
  | { kind: "chat"; text: string };

/** Split a raw input line into a slash command or a chat message.
 *  Returns null for empty input (caller should no-op). A lone "/" → /help. */
export function parseCommand(input: string): ParsedCommand | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("/")) {
    const body = trimmed.slice(1).trim();
    if (!body) return { kind: "slash", name: "help", args: [] };
    const parts = body.split(/\s+/);
    return { kind: "slash", name: parts[0].toLowerCase(), args: parts.slice(1) };
  }
  return { kind: "chat", text: trimmed };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- parseCommand`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/commands/parseCommand.ts zendaya-hud-react/src/__tests__/parseCommand.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add parseCommand (slash vs chat)"
git status --short
```
Confirm only the two intended files are in the commit; no protected paths staged.

---

## Task 2: hudControls (shared HUD mutations)

**Files:**
- Create: `zendaya-hud-react/src/commands/hudControls.ts`
- Test: `zendaya-hud-react/src/__tests__/hudControls.test.ts`

These functions are the exact mutations the WS `dispatchAction` performs today (see `useWebSocket.ts` lines 139-210), lifted into one reusable module so both the slash layer and the WS handler share them.

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/hudControls.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import {
  openMap, goHome, openModule, setThemeById,
  dock, undock, minimize, restore, activateVoice, deactivateVoice,
} from "../commands/hudControls";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    dockCorner: "br", minimized: false, voiceActive: false, activeThemeId: "forge",
  });
});

describe("hudControls", () => {
  it("openMap sets the map scene", () => {
    openMap();
    const s = useZendaya.getState();
    expect(s.scene).toBe("map");
    expect(s.activeModule).toBe("map");
    expect(s.panel).toBe("globe");
  });
  it("goHome resets to idle", () => {
    openMap();
    goHome();
    const s = useZendaya.getState();
    expect(s.scene).toBe("main");
    expect(s.activeModule).toBe("none");
    expect(s.panel).toBe("none");
  });
  it("openModule activates a valid module and ignores unknown ones", () => {
    openModule("clock");
    expect(useZendaya.getState().activeModule).toBe("clock");
    openModule("bogus");
    expect(useZendaya.getState().activeModule).toBe("clock"); // unchanged
  });
  it("openModule applies a valid corner", () => {
    openModule("weather", "bl");
    expect(useZendaya.getState().dockCorner).toBe("bl");
    expect(useZendaya.getState().activeModule).toBe("weather");
  });
  it("setThemeById switches a known theme and ignores unknown", () => {
    setThemeById("iris");
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    setThemeById("nope");
    expect(useZendaya.getState().activeThemeId).toBe("iris"); // unchanged
  });
  it("dock/undock, minimize/restore, voice toggles", () => {
    dock(); expect(useZendaya.getState().docked).toBe(true);
    undock(); expect(useZendaya.getState().docked).toBe(false);
    minimize(); expect(useZendaya.getState().minimized).toBe(true);
    restore(); expect(useZendaya.getState().minimized).toBe(false);
    activateVoice(); expect(useZendaya.getState().voiceActive).toBe(true);
    deactivateVoice(); expect(useZendaya.getState().voiceActive).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- hudControls`
Expected: FAIL — cannot find module `../commands/hudControls`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/commands/hudControls.ts`:

```ts
import { useZendaya, type ModuleId } from "../store/zendayaStore";

const MODULES: ModuleId[] = ["map", "calculator", "clock", "notes", "weather"];

/** Open the world-map scene. */
export function openMap() {
  const z = useZendaya.getState();
  z.setScene("map");
  z.setActiveModule("map");
  z.setPanel("globe");
}

/** Reset to the idle hologram (closes any map/module/panel). */
export function goHome() {
  const z = useZendaya.getState();
  z.setScene("main");
  z.setActiveModule("none");
  z.setPanel("none");
}

/** Activate a module by id; ignores unknown ids. `corner` (bl/br) is optional. */
export function openModule(name: string, corner?: string) {
  const z = useZendaya.getState();
  if (!MODULES.includes(name as ModuleId)) return;
  if (corner === "bl" || corner === "br") z.setDockCorner(corner);
  z.setActiveModule(name as ModuleId);
  if (name === "map") {
    z.setScene("map");
    z.setPanel("globe");
  }
}

/** Switch theme by id. setTheme silently ignores unknown ids. */
export function setThemeById(id: string) {
  useZendaya.getState().setTheme(id);
}

export function dock() { useZendaya.getState().setDocked(true); }
export function undock() { useZendaya.getState().setDocked(false); }
export function minimize() { useZendaya.getState().setMinimized(true); }
export function restore() { useZendaya.getState().setMinimized(false); }
export function activateVoice() { useZendaya.getState().setVoiceActive(true); }
export function deactivateVoice() { useZendaya.getState().setVoiceActive(false); }
export function showTerminal() { useZendaya.getState().setTerminalOpen(true); }
export function hideTerminal() { useZendaya.getState().setTerminalOpen(false); }
export function showNotification(text: string) {
  if (text) useZendaya.getState().pushNotification(text);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- hudControls`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/commands/hudControls.ts zendaya-hud-react/src/__tests__/hudControls.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add shared hudControls module"
git status --short
```

---

## Task 3: slashRegistry (runSlash)

**Files:**
- Create: `zendaya-hud-react/src/commands/slashRegistry.ts`
- Test: `zendaya-hud-react/src/__tests__/slashRegistry.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/slashRegistry.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { runSlash } from "../commands/slashRegistry";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    minimized: false, voiceActive: false, activeThemeId: "forge",
  });
});

describe("runSlash", () => {
  it("unknown command returns a hint and changes nothing", () => {
    const msg = runSlash("frobnicate", []);
    expect(msg).toContain("unknown command");
    expect(useZendaya.getState().scene).toBe("main");
  });
  it("/theme iris switches theme and confirms", () => {
    const msg = runSlash("theme", ["iris"]);
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    expect(msg).toContain("iris");
  });
  it("/theme with bad id reports it and does not switch", () => {
    const msg = runSlash("theme", ["banana"]);
    expect(msg).toContain("unknown theme");
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
  it("/theme with no arg returns usage", () => {
    expect(runSlash("theme", [])).toContain("usage");
  });
  it("/map opens the map", () => {
    runSlash("map", []);
    expect(useZendaya.getState().scene).toBe("map");
  });
  it("/home resets", () => {
    runSlash("map", []);
    runSlash("home", []);
    expect(useZendaya.getState().scene).toBe("main");
    expect(useZendaya.getState().activeModule).toBe("none");
  });
  it("/voice on and off toggle voiceActive", () => {
    runSlash("voice", ["on"]);
    expect(useZendaya.getState().voiceActive).toBe(true);
    runSlash("voice", ["off"]);
    expect(useZendaya.getState().voiceActive).toBe(false);
  });
  it("/voice with no arg returns usage", () => {
    expect(runSlash("voice", [])).toContain("usage");
  });
  it("/help lists commands", () => {
    expect(runSlash("help", [])).toContain("/theme");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- slashRegistry`
Expected: FAIL — cannot find module `../commands/slashRegistry`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/commands/slashRegistry.ts`:

```ts
import { THEMES, THEME_ORDER } from "../themes/registry";
import {
  openMap, goHome, openModule, setThemeById,
  dock, undock, minimize, restore, activateVoice, deactivateVoice,
} from "./hudControls";

interface SlashCommand {
  help: string;
  run: (args: string[]) => string;
}

export const SLASH_COMMANDS: Record<string, SlashCommand> = {
  theme: {
    help: `/theme <${THEME_ORDER.join("|")}> — switch theme`,
    run: (args) => {
      const id = (args[0] || "").toLowerCase();
      if (!id) return `usage: /theme <${THEME_ORDER.join("|")}>`;
      if (!THEMES[id]) return `unknown theme: ${id}`;
      setThemeById(id);
      return `→ theme set to ${id}`;
    },
  },
  map: { help: "/map — open the world map", run: () => { openMap(); return "→ opening map"; } },
  weather: { help: "/weather — open the weather scene", run: () => { openModule("weather"); return "→ opening weather"; } },
  clock: { help: "/clock — open the clock", run: () => { openModule("clock"); return "→ opening clock"; } },
  home: { help: "/home — return to idle", run: () => { goHome(); return "→ home"; } },
  dock: { help: "/dock — dock the orb", run: () => { dock(); return "→ docked"; } },
  undock: { help: "/undock — undock the orb", run: () => { undock(); return "→ undocked"; } },
  minimize: { help: "/minimize — minimize the HUD", run: () => { minimize(); return "→ minimized"; } },
  restore: { help: "/restore — restore the HUD", run: () => { restore(); return "→ restored"; } },
  voice: {
    help: "/voice <on|off> — toggle the mic visualizer",
    run: (args) => {
      const v = (args[0] || "").toLowerCase();
      if (v === "on") { activateVoice(); return "→ voice on"; }
      if (v === "off") { deactivateVoice(); return "→ voice off"; }
      return "usage: /voice <on|off>";
    },
  },
  help: {
    help: "/help — list commands",
    run: () => "commands: " + Object.keys(SLASH_COMMANDS).map((c) => "/" + c).join(", "),
  },
};

/** Execute a slash command by name; returns a transcript message. */
export function runSlash(name: string, args: string[]): string {
  const cmd = SLASH_COMMANDS[name];
  if (!cmd) return `unknown command: /${name} (try /help)`;
  return cmd.run(args);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- slashRegistry`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/commands/slashRegistry.ts zendaya-hud-react/src/__tests__/slashRegistry.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add slash command registry"
git status --short
```

---

## Task 4: backend.sendChat (POST /chat)

**Files:**
- Create: `zendaya-hud-react/src/api/backend.ts`
- Test: `zendaya-hud-react/src/__tests__/backend.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/backend.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChat, backendHttpOrigin } from "../api/backend";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("backendHttpOrigin", () => {
  it("derives an http origin (default)", () => {
    expect(backendHttpOrigin()).toBe("http://127.0.0.1:7475");
  });
});

describe("sendChat", () => {
  it("POSTs the message as JSON to /chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);

    await sendChat("hello zendaya");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/chat");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ message: "hello zendaya" });
  });

  it("rejects on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(sendChat("x")).rejects.toThrow(/500/);
  });

  it("rejects when fetch itself throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    await expect(sendChat("x")).rejects.toThrow(/network down/);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- backend`
Expected: FAIL — cannot find module `../api/backend`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/api/backend.ts`:

```ts
// Mirrors the WS URL resolution in useWebSocket.ts so the HTTP origin always
// matches the socket the HUD is connected to.
const WS_URL =
  new URLSearchParams(location.search).get("ws") || "ws://127.0.0.1:7475/ws";

/** The http(s) origin of the state server, derived from the WS URL. */
export function backendHttpOrigin(): string {
  try {
    const u = new URL(WS_URL);
    const proto = u.protocol === "wss:" ? "https:" : "http:";
    return `${proto}//${u.host}`;
  } catch {
    return "http://127.0.0.1:7475";
  }
}

/** POST a natural-language command to the backend's /chat handler. */
export async function sendChat(text: string): Promise<void> {
  const res = await fetch(`${backendHttpOrigin()}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- backend`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/api/backend.ts zendaya-hud-react/src/__tests__/backend.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add backend sendChat client"
git status --short
```

---

## Task 5: terminalLog store slice

**Files:**
- Modify: `zendaya-hud-react/src/store/zendayaStore.ts`
- Test: `zendaya-hud-react/src/__tests__/terminalLog.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/terminalLog.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => {
  useZendaya.getState().clearTerminalLog();
});

describe("terminalLog", () => {
  it("starts empty", () => {
    expect(useZendaya.getState().terminalLog).toEqual([]);
  });
  it("pushTerminalLine appends a line with role/text and a unique id", () => {
    useZendaya.getState().pushTerminalLine("user", "hi");
    useZendaya.getState().pushTerminalLine("zendaya", "hello");
    const log = useZendaya.getState().terminalLog;
    expect(log).toHaveLength(2);
    expect(log[0].role).toBe("user");
    expect(log[0].text).toBe("hi");
    expect(log[1].role).toBe("zendaya");
    expect(log[0].id).not.toBe(log[1].id);
  });
  it("caps the log at 100 lines", () => {
    for (let i = 0; i < 130; i++) useZendaya.getState().pushTerminalLine("system", String(i));
    const log = useZendaya.getState().terminalLog;
    expect(log).toHaveLength(100);
    expect(log[log.length - 1].text).toBe("129");
  });
  it("clearTerminalLog empties it", () => {
    useZendaya.getState().pushTerminalLine("user", "x");
    useZendaya.getState().clearTerminalLog();
    expect(useZendaya.getState().terminalLog).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- terminalLog`
Expected: FAIL — `clearTerminalLog is not a function` / `terminalLog` undefined.

- [ ] **Step 3: Write the implementation**

In `zendaya-hud-react/src/store/zendayaStore.ts`:

(a) After the `BodyAction` type (after line 69), add the terminal types:

```ts
export type TerminalRole = "user" | "zendaya" | "system";
export interface TerminalLine { id: number; role: TerminalRole; text: string; ts: number; }
```

(b) In the `ZendayaState` interface, add to the state fields (e.g. right after `nowPlaying: NowPlaying | null;` on line 93):

```ts
  terminalLog: TerminalLine[];
```

(c) In the `ZendayaState` interface setters block (e.g. after `setNowPlaying` on line 133), add:

```ts
  pushTerminalLine: (role: TerminalRole, text: string) => void;
  clearTerminalLog: () => void;
```

(d) Change the id-counter line (currently `let _nid = 0;` on line 148) to add a terminal id counter:

```ts
let _nid = 0;
let _tid = 0;
```

(e) In the `create(...)` initial state, after `nowPlaying: null,` (line 167) add:

```ts
  terminalLog: [],
```

(f) In the `create(...)` implementations, after the `setNowPlaying` implementation (ends line 206) add:

```ts
  pushTerminalLine: (role, text) =>
    set((s) => ({
      terminalLog: [
        ...s.terminalLog,
        { id: ++_tid, role, text, ts: Date.now() },
      ].slice(-100),
    })),
  clearTerminalLog: () => set({ terminalLog: [] }),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- terminalLog`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/store/zendayaStore.ts zendaya-hud-react/src/__tests__/terminalLog.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add in-session terminalLog store slice"
git status --short
```

---

## Task 6: Refactor dispatchAction to use hudControls

**Files:**
- Modify: `zendaya-hud-react/src/hooks/useWebSocket.ts` (the `dispatchAction` function, lines 139-210)
- Test: `zendaya-hud-react/src/__tests__/dispatchAction.test.ts`

Goal: remove duplicated mutation logic so the WS handler and the slash layer share `hudControls`. Behavior must stay identical. We export `dispatchAction` so it can be tested directly.

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/dispatchAction.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { dispatchAction } from "../hooks/useWebSocket";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    minimized: false, voiceActive: false, terminalOpen: false, activeThemeId: "forge",
  });
});

describe("dispatchAction", () => {
  it("open_map opens the map scene", () => {
    dispatchAction("open_map", {});
    const s = useZendaya.getState();
    expect(s.scene).toBe("map");
    expect(s.panel).toBe("globe");
  });
  it("open_module with a corner docks to that corner", () => {
    dispatchAction("open_module", { name: "weather", corner: "bl" });
    expect(useZendaya.getState().activeModule).toBe("weather");
    expect(useZendaya.getState().dockCorner).toBe("bl");
  });
  it("close_module returns home", () => {
    dispatchAction("open_map", {});
    dispatchAction("close_module", {});
    expect(useZendaya.getState().activeModule).toBe("none");
    expect(useZendaya.getState().scene).toBe("main");
  });
  it("show_terminal / hide_terminal toggle terminalOpen", () => {
    dispatchAction("show_terminal", {});
    expect(useZendaya.getState().terminalOpen).toBe(true);
    dispatchAction("hide_terminal", {});
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });
  it("set_theme switches theme", () => {
    dispatchAction("set_theme", { name: "iris" });
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });
  it("unknown action is a no-op", () => {
    dispatchAction("does_not_exist", {});
    expect(useZendaya.getState().scene).toBe("main");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- dispatchAction`
Expected: FAIL — `dispatchAction` is not exported from `../hooks/useWebSocket`.

- [ ] **Step 3: Rewrite dispatchAction**

In `zendaya-hud-react/src/hooks/useWebSocket.ts`, replace the entire `dispatchAction` function (lines 136-210, the comment block + function) with this. Also remove the now-unused `ModuleId` and `DockCorner` imports from line 2 **only if** they are no longer referenced elsewhere in the file (they are used only by the old `dispatchAction`, so remove them from the import).

Replace the import on line 2:

```ts
import { useZendaya, type AiState, type BodyAction } from "../store/zendayaStore";
```

Add this import near the other imports at the top of the file (after line 3):

```ts
import {
  openMap, goHome, openModule, setThemeById, dock, undock,
  showTerminal, hideTerminal, activateVoice, deactivateVoice,
  minimize, restore, showNotification,
} from "../commands/hudControls";
```

Replace the comment + function body (lines 136-210):

```ts
// Blueprint actions → store mutations, routed through the shared hudControls
// module (the same functions the in-HUD slash commands use). The visual
// reactions themselves live in the scene + chrome components which subscribe to
// the store and animate on change.
export function dispatchAction(action: string, payload: Record<string, any>) {
  switch (action) {
    case "open_map":
      openMap();
      break;
    case "close_map":
      goHome();
      break;
    case "open_module":
      openModule(
        typeof payload.name === "string" ? payload.name : "",
        typeof payload.corner === "string" ? payload.corner : undefined,
      );
      break;
    case "close_module":
      goHome();
      break;
    case "dock_orb":
      dock();
      break;
    case "undock_orb":
      undock();
      break;
    case "show_terminal":
      showTerminal();
      break;
    case "hide_terminal":
      hideTerminal();
      break;
    case "activate_voice":
      activateVoice();
      break;
    case "deactivate_voice":
      deactivateVoice();
      break;
    case "minimize_ui":
      minimize();
      break;
    case "restore_ui":
      restore();
      break;
    case "show_notification":
      showNotification(typeof payload.text === "string" ? payload.text : "");
      break;
    case "set_theme":
      setThemeById(typeof payload.name === "string" ? payload.name : "");
      break;
    default:
      // unknown action — ignore silently
      break;
  }
}
```

Note: the old `open_module` validated the name against a `ModuleId[]` list — that validation now lives inside `hudControls.openModule`, so behavior is preserved.

- [ ] **Step 4: Run the test + the full suite**

Run: `npm --prefix zendaya-hud-react run test -- dispatchAction`
Expected: PASS (6 tests).

Run: `npm --prefix zendaya-hud-react run test`
Expected: the whole suite stays green (no regression from the refactor).

- [ ] **Step 5: Typecheck**

Run: `npm --prefix zendaya-hud-react run build`
Expected: exit 0 (confirms the removed `ModuleId`/`DockCorner` imports aren't referenced elsewhere).

- [ ] **Step 6: Commit**

```bash
git add zendaya-hud-react/src/hooks/useWebSocket.ts zendaya-hud-react/src/__tests__/dispatchAction.test.ts
git -c commit.gpgsign=false commit -m "refactor(hud): route dispatchAction through shared hudControls"
git status --short
```

---

## Task 7: useCommandHotkey

**Files:**
- Create: `zendaya-hud-react/src/hooks/useCommandHotkey.ts`
- Test: `zendaya-hud-react/src/__tests__/useCommandHotkey.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/useCommandHotkey.test.tsx`:

```tsx
import { beforeEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { act } from "react";
import { useZendaya } from "../store/zendayaStore";
import { useCommandHotkey } from "../hooks/useCommandHotkey";

function Harness() {
  useCommandHotkey();
  return null;
}

beforeEach(() => {
  useZendaya.setState({ terminalOpen: false });
});

describe("useCommandHotkey", () => {
  it("Ctrl+K toggles the terminal open then closed", () => {
    render(<Harness />);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(true);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });

  it("Escape closes an open terminal", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<Harness />);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- useCommandHotkey`
Expected: FAIL — cannot find module `../hooks/useCommandHotkey`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/hooks/useCommandHotkey.ts`:

```ts
import { useEffect } from "react";
import { useZendaya } from "../store/zendayaStore";

/** Global keyboard control for the command terminal:
 *  Ctrl/Cmd+K toggles it; Escape closes it when open. */
export function useCommandHotkey() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const s = useZendaya.getState();
        s.setTerminalOpen(!s.terminalOpen);
      } else if (e.key === "Escape" && useZendaya.getState().terminalOpen) {
        useZendaya.getState().setTerminalOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- useCommandHotkey`
Expected: PASS (2 tests).

If `import { act } from "react"` is unavailable in this React version, change it to `import { act } from "@testing-library/react"` and re-run.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/hooks/useCommandHotkey.ts zendaya-hud-react/src/__tests__/useCommandHotkey.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): add Ctrl+K / Esc command-terminal hotkey"
git status --short
```

---

## Task 8: CommandTerminal overlay component

**Files:**
- Create: `zendaya-hud-react/src/components/HUD/CommandTerminal.tsx`
- Test: `zendaya-hud-react/src/__tests__/CommandTerminal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/CommandTerminal.test.tsx`:

```tsx
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import CommandTerminal from "../components/HUD/CommandTerminal";

beforeEach(() => {
  useZendaya.setState({
    terminalOpen: false, activeThemeId: "forge", scene: "main",
    activeModule: "none", panel: "none", connected: true,
  });
  useZendaya.getState().clearTerminalLog();
});

describe("CommandTerminal", () => {
  it("renders nothing when the terminal is closed", () => {
    render(<CommandTerminal />);
    expect(screen.queryByTestId("command-input")).toBeNull();
  });

  it("renders the input when open", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<CommandTerminal />);
    expect(screen.getByTestId("command-input")).toBeTruthy();
  });

  it("renders transcript lines from the store", () => {
    useZendaya.setState({ terminalOpen: true });
    useZendaya.getState().pushTerminalLine("system", "hello from system");
    render(<CommandTerminal />);
    expect(screen.getByText("hello from system")).toBeTruthy();
  });

  it("submitting a slash command runs it and logs user + system lines", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<CommandTerminal />);
    const input = screen.getByTestId("command-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "/theme iris" } });
    fireEvent.submit(input.closest("form")!);
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    const roles = useZendaya.getState().terminalLog.map((l) => l.role);
    expect(roles).toContain("user");
    expect(roles).toContain("system");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- CommandTerminal`
Expected: FAIL — cannot find module `../components/HUD/CommandTerminal`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/components/HUD/CommandTerminal.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { useZendaya } from "../../store/zendayaStore";
import { parseCommand } from "../../commands/parseCommand";
import { runSlash } from "../../commands/slashRegistry";
import { sendChat } from "../../api/backend";
import { useCommandHotkey } from "../../hooks/useCommandHotkey";

const OFFLINE_MSG = "⚠ can't reach Zendaya (is the backend running?)";

export default function CommandTerminal() {
  useCommandHotkey();

  const open = useZendaya((s) => s.terminalOpen);
  const log = useZendaya((s) => s.terminalLog);
  const text = useZendaya((s) => s.text);
  const connected = useZendaya((s) => s.connected);
  const push = useZendaya((s) => s.pushTerminalLine);

  const [input, setInput] = useState("");
  const awaiting = useRef(false);
  const prevText = useRef(text);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Echo Zendaya's reply (broadcast as `text`) into the transcript once, after
  // a chat line was submitted. Ignores the value present at mount.
  useEffect(() => {
    if (text !== prevText.current) {
      prevText.current = text;
      if (awaiting.current && text) {
        push("zendaya", text);
        awaiting.current = false;
      }
    }
  }, [text, push]);

  // Focus the input + scroll to the latest line when opened or on new lines.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log.length]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = parseCommand(input);
    if (!parsed) return;
    push("user", input.trim());
    setInput("");
    if (parsed.kind === "slash") {
      push("system", runSlash(parsed.name, parsed.args));
      return;
    }
    // chat
    if (!connected) {
      push("system", OFFLINE_MSG);
      return;
    }
    awaiting.current = true;
    sendChat(parsed.text).catch(() => {
      awaiting.current = false;
      push("system", OFFLINE_MSG);
    });
  }

  if (!open) return null;

  return (
    <div className="zen-terminal" data-testid="command-terminal">
      <div className="zen-terminal-log" ref={logRef}>
        {log.length === 0 && (
          <div className="zen-terminal-line-system">
            Type a command or talk to Zendaya. Try <strong>/help</strong>.
          </div>
        )}
        {log.map((line) => (
          <div key={line.id} className={`zen-terminal-line-${line.role}`}>
            {line.role === "user" ? "› " : line.role === "zendaya" ? "Zendaya: " : ""}
            {line.text}
          </div>
        ))}
      </div>
      <form className="zen-terminal-form" onSubmit={handleSubmit}>
        <span className="zen-terminal-prompt">›</span>
        <input
          ref={inputRef}
          data-testid="command-input"
          className="zen-terminal-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={connected ? "message or /command…" : "offline — /commands still work"}
          autoComplete="off"
          spellCheck={false}
        />
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- CommandTerminal`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/components/HUD/CommandTerminal.tsx zendaya-hud-react/src/__tests__/CommandTerminal.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): add CommandTerminal overlay"
git status --short
```

---

## Task 9: Mount in App + terminal CSS

**Files:**
- Modify: `zendaya-hud-react/src/App.tsx`
- Modify: `zendaya-hud-react/src/index.css`

No new unit test (App has no test harness; covered by build + live smoke in Task 10).

- [ ] **Step 1: Add the CSS**

Append to the end of `zendaya-hud-react/src/index.css`:

```css
/* ── Command terminal (SP-1) ───────────────────────────── */
.zen-terminal {
  position: fixed;
  left: 50%;
  bottom: 8%;
  transform: translateX(-50%);
  width: min(680px, 92vw);
  max-height: 46vh;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, #000 78%, transparent);
  border: 1px solid color-mix(in srgb, var(--zen-primary) 60%, transparent);
  border-radius: 10px;
  box-shadow: 0 0 24px color-mix(in srgb, var(--zen-primary) 30%, transparent);
  backdrop-filter: blur(6px);
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  color: var(--zen-primary);
  z-index: 60;
  overflow: hidden;
}
.zen-terminal-log {
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  line-height: 1.45;
}
.zen-terminal-line-user { color: var(--zen-accent); }
.zen-terminal-line-zendaya { color: #e9f6ff; }
.zen-terminal-line-system {
  color: color-mix(in srgb, var(--zen-primary) 70%, #888);
  font-style: italic;
}
.zen-terminal-form {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid color-mix(in srgb, var(--zen-primary) 30%, transparent);
  padding: 8px 12px;
}
.zen-terminal-prompt { color: var(--zen-accent); font-weight: 600; }
.zen-terminal-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--zen-primary);
  font-family: inherit;
  font-size: 14px;
}
.zen-terminal-input::placeholder {
  color: color-mix(in srgb, var(--zen-primary) 45%, transparent);
}
```

- [ ] **Step 2: Mount the component**

In `zendaya-hud-react/src/App.tsx`:

(a) Add the import after the other component imports (after line 11, `import WeatherReadout ...`):

```ts
import CommandTerminal from "./components/HUD/CommandTerminal";
```

(b) Mount it at the root level so it works even when the HUD overlay is minimized. Change the `<Atmosphere />` line (line 79) region to:

```tsx
        <Atmosphere />
        <CommandTerminal />
```

(The terminal renders `null` when closed, so it is inert until summoned.)

- [ ] **Step 3: Build to verify it compiles**

Run: `npm --prefix zendaya-hud-react run build`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add zendaya-hud-react/src/App.tsx zendaya-hud-react/src/index.css
git -c commit.gpgsign=false commit -m "feat(hud): mount CommandTerminal + terminal styles"
git status --short
```

---

## Task 10: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `npm --prefix zendaya-hud-react run test`
Expected: all tests pass (the prior 115 + the new SP-1 tests: parseCommand 6, hudControls 6, slashRegistry 9, backend 4, terminalLog 4, dispatchAction 6, useCommandHotkey 2, CommandTerminal 4).

- [ ] **Step 2: Clean build**

Run: `npm --prefix zendaya-hud-react run build`
Expected: exit 0, no type errors.

- [ ] **Step 3: Live smoke (manual, backend running)**

Start the dev server (`npm --prefix zendaya-hud-react run dev`) with the backend up, then verify:
- Ctrl+K opens the terminal; Esc closes it.
- `/theme iris` flips the theme instantly (no network); `/map`, `/clock`, `/weather`, `/home` switch scenes; `/help` lists commands; an unknown `/xyz` shows the hint.
- A natural-language line (e.g. "what's the weather like?") appears as a `user` line, reaches the backend, and Zendaya's reply echoes as a `zendaya` line — and she still speaks/reacts through the existing backend path.
- With the backend stopped, a chat line shows the offline message while slash commands still work.
- Driving the store from the console: `useZendaya.getState().setTerminalOpen(true)` opens it, confirming the `show_terminal` WS action path.

- [ ] **Step 4: Protected-path audit**

Run: `git status --short`
Confirm the only committed changes across SP-1 are under `zendaya-hud-react/src/` and `docs/`. Confirm the pre-existing diff (`backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`) remains **unstaged and unchanged**, and nothing under `.claude/` or `.superpowers/` was staged.

- [ ] **Step 5: Done**

SP-1 is complete. Report the delivered command bridge and tee up SP-2 (Voice from the HUD) or SP-3 (In-HUD music player) for the next design cycle.

---

## Self-Review notes (author)

- **Spec coverage:** hybrid model (Tasks 3+8), terminal overlay + summon (Tasks 7-9, reuses `terminalOpen`), `POST /chat` chat path + reply echo (Tasks 4+8), slash set (Task 3), `hudControls` shared with `dispatchAction` (Tasks 2+6), zero backend edits (enforced in every commit step), error handling (offline + bad-arg in Tasks 3+8), test strategy (every pure unit + light DOM). All spec done-criteria map to tasks.
- **Type consistency:** `ParsedCommand`, `TerminalRole`/`TerminalLine`, `pushTerminalLine(role,text)`, `runSlash(name,args)`, `sendChat(text)`, and the `hudControls` function names are used identically across Tasks 1-9.
- **No placeholders:** every code/test step contains complete copy-pasteable content.
