import { describe, it, expect } from "vitest";
import { THEMES, THEME_ORDER } from "../themes/registry";
import type { ChromeStyle } from "../themes/types";

const REQUIRED_KEYS = [
  "id", "name", "primary", "accent", "bg", "textGlow",
  "sceneColor", "bloom", "chrome", "ambient", "grain",
] as const;
const VALID_CHROME: ChromeStyle[] = ["ring", "aperture", "gauge", "radar"];

describe("theme registry", () => {
  it("every theme has all required token fields", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      for (const k of REQUIRED_KEYS) {
        expect(t, `${key}.${k} missing`).toHaveProperty(k);
      }
    }
  });

  it("theme.id matches its registry key", () => {
    for (const [key, t] of Object.entries(THEMES)) expect(t.id).toBe(key);
  });

  it("chrome is a valid style", () => {
    for (const t of Object.values(THEMES)) expect(VALID_CHROME).toContain(t.chrome);
  });

  it("bg is a 2-tuple", () => {
    for (const t of Object.values(THEMES)) {
      expect(Array.isArray(t.bg)).toBe(true);
      expect(t.bg).toHaveLength(2);
    }
  });

  it("THEME_ORDER ids all exist in THEMES", () => {
    for (const id of THEME_ORDER) expect(THEMES[id]).toBeDefined();
  });

  it("ships forge and iris", () => {
    expect(THEMES.forge).toBeDefined();
    expect(THEMES.iris).toBeDefined();
  });
});
