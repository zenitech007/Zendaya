import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { runSlash } from "../commands/slashRegistry";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    minimized: false, voiceActive: false, activeThemeId: "forge",
  });
});

describe("runSlash", () => {
  it("unknown command returns a hint and changes nothing", () => {
    const msg = runSlash("frobnicate", []);
    expect(msg).toContain("unknown command");
    expect(useZendaya.getState().scene).toBe("main");
  });
  it("/theme iris switches theme and confirms", () => {
    const msg = runSlash("theme", ["iris"]);
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    expect(msg).toContain("iris");
  });
  it("/theme with bad id reports it and does not switch", () => {
    const msg = runSlash("theme", ["banana"]);
    expect(msg).toContain("unknown theme");
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
  it("/theme with no arg returns usage", () => {
    expect(runSlash("theme", [])).toContain("usage");
  });
  it("/map opens the map", () => {
    runSlash("map", []);
    expect(useZendaya.getState().scene).toBe("map");
  });
  it("/home resets", () => {
    runSlash("map", []);
    runSlash("home", []);
    expect(useZendaya.getState().scene).toBe("main");
    expect(useZendaya.getState().activeModule).toBe("none");
  });
  it("/voice on and off toggle voiceActive", () => {
    runSlash("voice", ["on"]);
    expect(useZendaya.getState().voiceActive).toBe(true);
    runSlash("voice", ["off"]);
    expect(useZendaya.getState().voiceActive).toBe(false);
  });
  it("/voice with no arg returns usage", () => {
    expect(runSlash("voice", [])).toContain("usage");
  });
  it("/help lists commands", () => {
    expect(runSlash("help", [])).toContain("/theme");
  });
});
