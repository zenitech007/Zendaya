import { describe, expect, it } from "vitest";
import { voicePlayer } from "../audio/voicePlayer";

describe("voicePlayer singleton", () => {
  it("exposes handle() and unlock()", () => {
    expect(typeof voicePlayer.handle).toBe("function");
    expect(typeof voicePlayer.unlock).toBe("function");
  });

  it("handle('stop') before any audio context is a no-op (no throw)", () => {
    expect(() => voicePlayer.handle({ event: "stop" })).not.toThrow();
  });

  it("ignores an unknown event shape without throwing", () => {
    expect(() => voicePlayer.handle({ event: "bogus" } as any)).not.toThrow();
    expect(() => voicePlayer.handle({} as any)).not.toThrow();
  });

  it("unlock() is safe when no AudioContext exists in the environment", () => {
    // happy-dom has no AudioContext; ensureCtx throws and unlock swallows it.
    const saved = (globalThis as any).AudioContext;
    delete (globalThis as any).AudioContext;
    expect(() => voicePlayer.unlock()).not.toThrow();
    if (saved) (globalThis as any).AudioContext = saved;
  });
});
