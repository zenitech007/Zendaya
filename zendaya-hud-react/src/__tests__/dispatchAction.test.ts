import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { dispatchAction } from "../hooks/useWebSocket";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    minimized: false, voiceActive: false, terminalOpen: false, activeThemeId: "forge",
  });
});

describe("dispatchAction", () => {
  it("open_map opens the map scene", () => {
    dispatchAction("open_map", {});
    const s = useZendaya.getState();
    expect(s.scene).toBe("map");
    expect(s.panel).toBe("globe");
  });
  it("open_module with a corner docks to that corner", () => {
    dispatchAction("open_module", { name: "weather", corner: "bl" });
    expect(useZendaya.getState().activeModule).toBe("weather");
    expect(useZendaya.getState().dockCorner).toBe("bl");
  });
  it("close_module returns home", () => {
    dispatchAction("open_map", {});
    dispatchAction("close_module", {});
    expect(useZendaya.getState().activeModule).toBe("none");
    expect(useZendaya.getState().scene).toBe("main");
  });
  it("show_terminal / hide_terminal toggle terminalOpen", () => {
    dispatchAction("show_terminal", {});
    expect(useZendaya.getState().terminalOpen).toBe(true);
    dispatchAction("hide_terminal", {});
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });
  it("set_theme switches theme", () => {
    dispatchAction("set_theme", { name: "iris" });
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });
  it("unknown action is a no-op", () => {
    dispatchAction("does_not_exist", {});
    expect(useZendaya.getState().scene).toBe("main");
  });
});
