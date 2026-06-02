import { describe, it, expect } from "vitest";
import {
  fibonacciSphere,
  valueNoise3,
  landMask,
  buildGlobePoints,
} from "../scenes/pointcloud";

describe("pointcloud", () => {
  it("fibonacciSphere returns count*3 floats all on the given radius", () => {
    const pts = fibonacciSphere(500, 1.5);
    expect(pts.length).toBe(1500);
    for (let i = 0; i < 500; i++) {
      const r = Math.hypot(pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2]);
      expect(r).toBeGreaterThan(1.49);
      expect(r).toBeLessThan(1.51);
    }
  });

  it("valueNoise3 is deterministic and within [0,1]", () => {
    const a = valueNoise3(1.2, 3.4, 5.6);
    const b = valueNoise3(1.2, 3.4, 5.6);
    expect(a).toBe(b);
    expect(a).toBeGreaterThanOrEqual(0);
    expect(a).toBeLessThanOrEqual(1);
  });

  it("landMask is normalized to [0,1]", () => {
    for (let i = 0; i < 50; i++) {
      const v = landMask(Math.sin(i), Math.cos(i * 1.3), Math.sin(i * 0.7));
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("buildGlobePoints returns matching positions and landness lengths", () => {
    const { positions, landness } = buildGlobePoints(1000, 1.5);
    expect(positions.length).toBe(3000);
    expect(landness.length).toBe(1000);
    for (let i = 0; i < 1000; i++) {
      expect(landness[i]).toBeGreaterThanOrEqual(0);
      expect(landness[i]).toBeLessThanOrEqual(1);
    }
  });
});
