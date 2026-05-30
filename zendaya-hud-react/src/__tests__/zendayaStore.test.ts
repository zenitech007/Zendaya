import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { normaliseVisemes } from "../store/normaliseVisemes";

describe("zendayaStore — new slices", () => {
  beforeEach(() => {
    // Reset to defaults
    useZendaya.setState({
      visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
      telemetry: null,
      perception: null,
      bodyActionPulse: { action: "", ts: 0 },
    });
  });

  it("setVisemes mutates the visemes slice", () => {
    useZendaya.getState().setVisemes({ aa: 0.5, ih: 0, ee: 0, oh: 0, ou: 0 });
    expect(useZendaya.getState().visemes.aa).toBeCloseTo(0.5);
  });

  it("setTelemetry stores the payload", () => {
    const payload = {
      cpu: 23.5, mem: 60, mic_level: 0, mood: "neutral",
      vision_active: false, gestures_active: false,
      hud_enabled: true, online: true,
      user_name: "Ikenna", language: "english",
      last_gesture: { name: "none", ts: 0 },
    };
    useZendaya.getState().setTelemetry(payload);
    expect(useZendaya.getState().telemetry).toEqual(payload);
  });

  it("setPerception stores the payload", () => {
    const payload = {
      face: { present: true, ts: 1 },
      last_gesture: { name: "Thumb_Up", ts: 2 },
    };
    useZendaya.getState().setPerception(payload);
    expect(useZendaya.getState().perception).toEqual(payload);
  });

  it("firePulseBodyAction sets action and ts", () => {
    useZendaya.getState().firePulseBodyAction("nod");
    const p = useZendaya.getState().bodyActionPulse;
    expect(p.action).toBe("nod");
    expect(p.ts).toBeGreaterThan(0);
  });

  it("firePulseBodyAction increments ts on repeat", async () => {
    useZendaya.getState().firePulseBodyAction("nod");
    const t1 = useZendaya.getState().bodyActionPulse.ts;
    await new Promise((r) => setTimeout(r, 5));
    useZendaya.getState().firePulseBodyAction("nod");
    const t2 = useZendaya.getState().bodyActionPulse.ts;
    expect(t2).toBeGreaterThan(t1);
  });
});

describe("normaliseVisemes", () => {
  it("clamps to [0, 1]", () => {
    const result = normaliseVisemes({ aa: 1.5, ih: -0.2, ee: 0.5, oh: 0, ou: 0 });
    expect(result.aa).toBe(1);
    expect(result.ih).toBe(0);
    expect(result.ee).toBeCloseTo(0.5);
  });

  it("replaces NaN with 0", () => {
    const result = normaliseVisemes({ aa: NaN, ih: 0, ee: 0, oh: 0, ou: 0 });
    expect(result.aa).toBe(0);
  });

  it("fills missing keys with 0", () => {
    const result = normaliseVisemes({ aa: 0.5 } as any);
    expect(result.ih).toBe(0);
    expect(result.ee).toBe(0);
    expect(result.oh).toBe(0);
    expect(result.ou).toBe(0);
  });
});
