import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Vitest runs with cwd = the package root (zendaya-hud-react).
const root = process.cwd();
const read = (rel: string) => readFileSync(resolve(root, rel), "utf8");

// Per-file list of retired hard-coded literals that must no longer appear.
const BANNED: Record<string, string[]> = {
  "src/index.css": ["168, 85, 247", "168,85,247"],
  "src/components/HUD/MusicPlayer.tsx": ["168,85,247", "168, 85, 247", "#ec4899", "#a855f7"],
  "src/components/Modules/ModulePanel.tsx": ["255,138,60", "255, 138, 60", "#ff8a3c"],
  "src/components/Modules/Notes.tsx": ["255,138,60", "255, 138, 60"],
};

describe("reskin guard — retired theme literals are gone", () => {
  for (const [file, literals] of Object.entries(BANNED)) {
    const src = read(file);
    for (const lit of literals) {
      it(`${file} no longer contains "${lit}"`, () => {
        expect(src).not.toContain(lit);
      });
    }
  }
});
