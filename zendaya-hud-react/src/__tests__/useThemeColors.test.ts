import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useThemeColors } from "../themes/useThemeColors";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("useThemeColors", () => {
  it("returns the forge scene color and bloom by default", () => {
    const { result } = renderHook(() => useThemeColors());
    expect(result.current.scene.getHexString()).toBe("ff8a3c");
    expect(result.current.bloom).toBe(1.3);
  });

  it("tracks a theme change to iris", () => {
    const { result } = renderHook(() => useThemeColors());
    act(() => useZendaya.setState({ activeThemeId: "iris" }));
    expect(result.current.scene.getHexString()).toBe("2fd6ff");
    expect(result.current.bloom).toBe(1.1);
  });

  it("falls back to forge for an unknown theme id", () => {
    useZendaya.setState({ activeThemeId: "nope" });
    const { result } = renderHook(() => useThemeColors());
    expect(result.current.scene.getHexString()).toBe("ff8a3c");
  });
});
