import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as THREE from "three";

vi.mock("gsap", () => {
  const tweens: any[] = [];
  const gsap = {
    to: vi.fn((target: any, vars: any) => {
      tweens.push({ target, vars, kind: "to" });
      return { vars };
    }),
    fromTo: vi.fn((target: any, from: any, to: any) => {
      tweens.push({ target, from, to, kind: "fromTo" });
      return {};
    }),
    killTweensOf: vi.fn(() => {
      // no-op
    }),
  };
  // expose for assertions
  (gsap as any).__tweens = tweens;
  return { default: gsap, ...gsap };
});

import gsap from "gsap";
import { useZendaya } from "../store/zendayaStore";
import { useBodyAction } from "../hooks/useBodyAction";

beforeEach(() => {
  (gsap as any).__tweens.length = 0;
  vi.mocked(gsap.to).mockClear();
  vi.mocked(gsap.killTweensOf).mockClear();
  useZendaya.setState({ bodyActionPulse: { action: "", ts: 0 } });
});

function makeGroup() {
  return { current: new THREE.Group() };
}

describe("useBodyAction", () => {
  it("no-op when pulse.action is empty", () => {
    const ref = makeGroup();
    renderHook(() => useBodyAction(ref));
    expect(gsap.to).not.toHaveBeenCalled();
  });

  it.each(["nod", "shake", "wave", "shrug"] as const)(
    "runs at least one tween for action %s",
    (action) => {
      const ref = makeGroup();
      renderHook(() => useBodyAction(ref));
      act(() => {
        useZendaya.setState({ bodyActionPulse: { action, ts: 1 } });
      });
      expect(gsap.to).toHaveBeenCalled();
    }
  );

  it("re-fires on ts change with same action", () => {
    const ref = makeGroup();
    renderHook(() => useBodyAction(ref));
    act(() => useZendaya.setState({ bodyActionPulse: { action: "nod", ts: 1 } }));
    const firstCallCount = vi.mocked(gsap.to).mock.calls.length;
    act(() => useZendaya.setState({ bodyActionPulse: { action: "nod", ts: 2 } }));
    expect(vi.mocked(gsap.to).mock.calls.length).toBeGreaterThan(firstCallCount);
  });
});
