import { describe, it, expect } from "vitest";
import { MORPH_MS, playChromeFx } from "../components/chrome/chromeFx";

function svg() {
  return document.createElementNS("http://www.w3.org/2000/svg", "svg") as SVGSVGElement;
}

describe("chromeFx", () => {
  it("MORPH_MS matches the 1.2s scene morph", () => {
    expect(MORPH_MS).toBe(1200);
  });

  for (const fx of ["aperture", "spin", "radar"] as const) {
    it(`${fx} timeline runs for the full morph window`, () => {
      const tl = playChromeFx(fx, svg());
      expect(tl.duration()).toBeCloseTo(1.2, 1);
      tl.kill();
    });
  }
});
