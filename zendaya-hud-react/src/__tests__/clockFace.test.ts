import { describe, it, expect } from "vitest";
import { presenceOf } from "../scenes/clock/faceCommon";
import { buildDigitPoints } from "../scenes/clock/digitFont";

describe("presenceOf", () => {
  it("is 0 before the morph passes 0.15", () => {
    expect(presenceOf(0.0, 1)).toBe(0);
    expect(presenceOf(0.1, 1)).toBe(0);
  });
  it("is fully present at progress 1 with fade 1", () => {
    expect(presenceOf(1.0, 1)).toBeCloseTo(1, 5);
  });
  it("is gated (multiplied) by the crossfade value", () => {
    expect(presenceOf(1.0, 0)).toBe(0);
    expect(presenceOf(1.0, 0.5)).toBeCloseTo(0.5, 5);
  });
});

describe("buildDigitPoints", () => {
  it("returns a Float32Array whose length is a multiple of 3", () => {
    const pts = buildDigitPoints("13:47");
    expect(pts).toBeInstanceOf(Float32Array);
    expect(pts.length % 3).toBe(0);
    expect(pts.length).toBeGreaterThan(0);
  });
  it("produces only finite coordinates", () => {
    const pts = buildDigitPoints("00:00");
    expect(pts.every((v) => Number.isFinite(v))).toBe(true);
  });
  it("falls back to a zero glyph for unknown characters", () => {
    expect(buildDigitPoints("X").length).toBeGreaterThan(0);
  });
});
