import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => {
  useZendaya.setState({ activeThemeId: "forge" });
});

describe("theme store slice", () => {
  it("default activeThemeId is forge", () => {
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });

  it("setTheme switches to a known theme", () => {
    useZendaya.getState().setTheme("iris");
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("setTheme ignores unknown ids", () => {
    useZendaya.getState().setTheme("nope");
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });

  it("cycleTheme advances and wraps", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    useZendaya.getState().cycleTheme();
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    useZendaya.getState().cycleTheme();
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
});
