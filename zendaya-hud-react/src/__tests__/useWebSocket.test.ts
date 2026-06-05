import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import { useWebSocket } from "../hooks/useWebSocket";
import { voicePlayer } from "../audio/voicePlayer";

class FakeWS extends EventTarget {
  static instances: FakeWS[] = [];
  readyState = 0; // CONNECTING
  url: string;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
    this.dispatchEvent(new Event("close"));
  });
  constructor(url: string) {
    super();
    this.url = url;
    FakeWS.instances.push(this);
    setTimeout(() => {
      this.readyState = 1;
      this.dispatchEvent(new Event("open"));
    }, 0);
  }
  fireMessage(data: any) {
    const ev = new MessageEvent("message", { data: JSON.stringify(data) });
    this.dispatchEvent(ev);
  }
}

beforeEach(() => {
  FakeWS.instances = [];
  (globalThis as any).WebSocket = FakeWS;
  useZendaya.setState({
    ai: "idle",
    text: "",
    audioLevel: 0,
    panel: "",
    nowPlaying: null,
    musicCmd: null,
    visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
    telemetry: null,
    perception: null,
    bodyActionPulse: { action: "", ts: 0 },
    activeThemeId: "forge",
  });
});

afterEach(() => {
  vi.useRealTimers();
});

async function freshHook() {
  const result = renderHook(() => useWebSocket());
  // Wait one microtask so the FakeWS open event fires.
  await Promise.resolve();
  await new Promise((r) => setTimeout(r, 5));
  const ws = FakeWS.instances[FakeWS.instances.length - 1];
  return { result, ws };
}

describe("useWebSocket — new message types", () => {
  it("amplitude updates audioLevel", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ amplitude: 0.7 });
    expect(useZendaya.getState().audioLevel).toBeCloseTo(0.7);
  });

  it("visemes payload populates the slice", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ visemes: { aa: 0.5, ih: 0, ee: 0, oh: 0, ou: 0 } });
    expect(useZendaya.getState().visemes.aa).toBeCloseTo(0.5);
  });

  it("telemetry payload populates the slice", async () => {
    const { ws } = await freshHook();
    const tel = {
      cpu: 30, mem: 50, mic_level: 0, mood: "neutral",
      vision_active: false, gestures_active: false,
      hud_enabled: true, online: true,
      user_name: "", language: "english",
      last_gesture: { name: "none", ts: 0 },
    };
    ws.fireMessage({ telemetry: tel });
    expect(useZendaya.getState().telemetry).toEqual(tel);
  });

  it("perception payload populates the slice", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ perception: { face: { present: true, ts: 1 }, last_gesture: { name: "Thumb_Up", ts: 2 } } });
    expect(useZendaya.getState().perception?.face.present).toBe(true);
  });

  it("body_action fires a pulse", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ body_action: "nod" });
    expect(useZendaya.getState().bodyActionPulse.action).toBe("nod");
    expect(useZendaya.getState().bodyActionPulse.ts).toBeGreaterThan(0);
  });
});

describe("useWebSocket — widened AI filter", () => {
  it.each(["idle", "aware", "listening", "thinking", "speaking", "searching", "mapping", "alert", "error"])(
    "accepts state '%s'",
    async (state) => {
      const { ws } = await freshHook();
      ws.fireMessage({ state });
      expect(useZendaya.getState().ai).toBe(state);
    }
  );
});

describe("useWebSocket — malformed payloads", () => {
  it("non-object telemetry is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ telemetry: 42 });
    expect(useZendaya.getState().telemetry).toBeNull();
  });

  it("non-object visemes is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ visemes: "bad" });
    expect(useZendaya.getState().visemes.aa).toBe(0);
  });

  it("invalid body_action string is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ body_action: "backflip" });
    expect(useZendaya.getState().bodyActionPulse.action).toBe("");
  });

  it("array visemes payload is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ visemes: [0.5, 0.2] });
    expect(useZendaya.getState().visemes.aa).toBe(0);
  });
});

describe("useWebSocket — set_theme action", () => {
  it("set_theme switches to a known theme", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "set_theme", payload: { name: "iris" } });
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("set_theme ignores an unknown theme name", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "set_theme", payload: { name: "bogus" } });
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });

  it("set_theme with a non-string name is ignored", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "set_theme", payload: { name: 42 } });
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
});

describe("useWebSocket — now_playing maps stream fields", () => {
  it("carries stream_url and track_id onto the store", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({
      now_playing: {
        track: "Song",
        artist: "Artist",
        is_playing: true,
        progress_ms: 0,
        duration_ms: 1000,
        source: "local",
        stream_url: "/music/stream/abc",
        track_id: "abc",
      },
    });
    const np = useZendaya.getState().nowPlaying!;
    expect(np.streamUrl).toBe("/music/stream/abc");
    expect(np.trackId).toBe("abc");
  });
});

describe("useWebSocket — music_control action", () => {
  it("a known cmd is pushed to musicCmd", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "music_control", payload: { cmd: "next" } });
    expect(useZendaya.getState().musicCmd?.cmd).toBe("next");
  });

  it("an unknown cmd is ignored", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "music_control", payload: { cmd: "explode" } });
    expect(useZendaya.getState().musicCmd).toBeNull();
  });
});

describe("useWebSocket — audio frames route to voicePlayer", () => {
  it("forwards an audio frame to voicePlayer.handle", async () => {
    const spy = vi.spyOn(voicePlayer, "handle").mockImplementation(() => {});
    const { ws } = await freshHook();
    ws.fireMessage({ audio: { event: "begin", rate: 22050, id: 1 } });
    expect(spy).toHaveBeenCalledWith({ event: "begin", rate: 22050, id: 1 });
    spy.mockRestore();
  });

  it("ignores a non-object audio field", async () => {
    const spy = vi.spyOn(voicePlayer, "handle").mockImplementation(() => {});
    const { ws } = await freshHook();
    ws.fireMessage({ audio: "nope" });
    ws.fireMessage({ audio: [1, 2, 3] });
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
