import { describe, it, expect } from "vitest";
import { wmoToForm, buildFormPoints } from "../scenes/weatherForms";

describe("wmoToForm", () => {
  it("maps clear codes", () => {
    expect(wmoToForm(0)).toBe("clear");
    expect(wmoToForm(1)).toBe("clear");
  });
  it("maps cloud codes", () => {
    expect(wmoToForm(2)).toBe("clouds");
    expect(wmoToForm(3)).toBe("clouds");
  });
  it("maps fog codes", () => {
    expect(wmoToForm(45)).toBe("fog");
    expect(wmoToForm(48)).toBe("fog");
  });
  it("maps rain codes (drizzle, rain, showers)", () => {
    expect(wmoToForm(51)).toBe("rain");
    expect(wmoToForm(63)).toBe("rain");
    expect(wmoToForm(80)).toBe("rain");
  });
  it("maps snow codes", () => {
    expect(wmoToForm(71)).toBe("snow");
    expect(wmoToForm(77)).toBe("snow");
    expect(wmoToForm(86)).toBe("snow");
  });
  it("maps thunderstorm codes", () => {
    expect(wmoToForm(95)).toBe("storm");
    expect(wmoToForm(99)).toBe("storm");
  });
  it("defaults unknown codes to clouds", () => {
    expect(wmoToForm(1234)).toBe("clouds");
    expect(wmoToForm(-1)).toBe("clouds");
  });
});

describe("buildFormPoints", () => {
  it("returns count*3 finite coordinates", () => {
    const pts = buildFormPoints("storm", 500);
    expect(pts).toBeInstanceOf(Float32Array);
    expect(pts.length).toBe(500 * 3);
    expect(pts.every((v) => Number.isFinite(v))).toBe(true);
  });
  it("differs between forms (geometry, not just color)", () => {
    const a = buildFormPoints("clear", 300);
    const b = buildFormPoints("storm", 300);
    let differing = 0;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) differing++;
    expect(differing).toBeGreaterThan(0);
  });
});
