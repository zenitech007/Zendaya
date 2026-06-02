import { describe, it, expect } from "vitest";
import { ambientParamsFor } from "../systems/ambientParams";

describe("ambientParamsFor", () => {
  it("forge and iris have distinct timbres", () => {
    const f = ambientParamsFor("forge");
    const i = ambientParamsFor("iris");
    expect(f.baseFreq).not.toBe(i.baseFreq);
    expect(f.airFreq).not.toBe(i.airFreq);
    expect(f.brightness).not.toBe(i.brightness);
  });

  it("returns in-range params for known themes", () => {
    for (const id of ["forge", "iris"]) {
      const p = ambientParamsFor(id);
      expect(p.baseFreq).toBeGreaterThanOrEqual(30);
      expect(p.baseFreq).toBeLessThanOrEqual(120);
      expect(p.airFreq).toBeGreaterThan(0);
      expect(p.harmonicMix).toBeGreaterThan(0);
      expect(p.brightness).toBeGreaterThan(0);
    }
  });

  it("falls back to forge for an unknown id", () => {
    expect(ambientParamsFor("nope")).toEqual(ambientParamsFor("forge"));
  });
});
