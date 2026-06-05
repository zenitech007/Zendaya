import { THEMES, THEME_ORDER } from "../themes/registry";
import {
  openMap, goHome, openModule, setThemeById,
  dock, undock, minimize, restore, activateVoice, deactivateVoice,
} from "./hudControls";
import { quit } from "../api/backend";

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
  quit: {
    help: "/quit — shut Zendaya down",
    run: () => { void quit(); return "→ shutting down Zendaya…"; },
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
