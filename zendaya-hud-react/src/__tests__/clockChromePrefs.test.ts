import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya, readPref } from "../store/zendayaStore";

beforeEach(() => {
  localStorage.clear();
  useZendaya.setState({ clockFace: "orbital", chromeFx: "aperture" });
});

describe("readPref", () => {
  it("returns the stored value when it is in the allow-list", () => {
    localStorage.setItem("k", "digits");
    expect(readPref("k", ["orbital", "digits", "analog"] as const, "orbital")).toBe("digits");
  });
  it("falls back when the stored value is not allowed", () => {
    localStorage.setItem("k", "bogus");
    expect(readPref("k", ["orbital", "digits", "analog"] as const, "orbital")).toBe("orbital");
  });
  it("falls back when nothing is stored", () => {
    expect(readPref("missing", ["aperture", "spin", "radar"] as const, "aperture")).toBe("aperture");
  });
});

describe("clock + chrome UI prefs", () => {
  it("default clockFace is orbital and chromeFx is aperture", () => {
    expect(useZendaya.getState().clockFace).toBe("orbital");
    expect(useZendaya.getState().chromeFx).toBe("aperture");
  });
  it("setClockFace updates state and persists to localStorage", () => {
    useZendaya.getState().setClockFace("analog");
    expect(useZendaya.getState().clockFace).toBe("analog");
    expect(localStorage.getItem("zendaya.hud.clockFace")).toBe("analog");
  });
  it("setChromeFx updates state and persists to localStorage", () => {
    useZendaya.getState().setChromeFx("radar");
    expect(useZendaya.getState().chromeFx).toBe("radar");
    expect(localStorage.getItem("zendaya.hud.chromeFx")).toBe("radar");
  });
});
