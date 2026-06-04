import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import {
  openMap, goHome, openModule, setThemeById,
  dock, undock, minimize, restore, activateVoice, deactivateVoice,
} from "../commands/hudControls";

beforeEach(() => {
  useZendaya.setState({
    scene: "main", panel: "none", activeModule: "none", docked: false,
    dockCorner: "br", minimized: false, voiceActive: false, activeThemeId: "forge",
  });
});

describe("hudControls", () => {
  it("openMap sets the map scene", () => {
    openMap();
    const s = useZendaya.getState();
    expect(s.scene).toBe("map");
    expect(s.activeModule).toBe("map");
    expect(s.panel).toBe("globe");
  });
  it("goHome resets to idle", () => {
    openMap();
    goHome();
    const s = useZendaya.getState();
    expect(s.scene).toBe("main");
    expect(s.activeModule).toBe("none");
    expect(s.panel).toBe("none");
  });
  it("openModule activates a valid module and ignores unknown ones", () => {
    openModule("clock");
    expect(useZendaya.getState().activeModule).toBe("clock");
    openModule("bogus");
    expect(useZendaya.getState().activeModule).toBe("clock"); // unchanged
  });
  it("openModule applies a valid corner", () => {
    openModule("weather", "bl");
    expect(useZendaya.getState().dockCorner).toBe("bl");
    expect(useZendaya.getState().activeModule).toBe("weather");
  });
  it("setThemeById switches a known theme and ignores unknown", () => {
    setThemeById("iris");
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    setThemeById("nope");
    expect(useZendaya.getState().activeThemeId).toBe("iris"); // unchanged
  });
  it("dock/undock, minimize/restore, voice toggles", () => {
    dock(); expect(useZendaya.getState().docked).toBe(true);
    undock(); expect(useZendaya.getState().docked).toBe(false);
    minimize(); expect(useZendaya.getState().minimized).toBe(true);
    restore(); expect(useZendaya.getState().minimized).toBe(false);
    activateVoice(); expect(useZendaya.getState().voiceActive).toBe(true);
    deactivateVoice(); expect(useZendaya.getState().voiceActive).toBe(false);
  });
});
