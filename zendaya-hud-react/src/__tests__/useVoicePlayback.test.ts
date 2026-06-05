import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { voicePlayer } from "../audio/voicePlayer";
import { useVoicePlayback } from "../hooks/useVoicePlayback";

afterEach(() => cleanup());

describe("useVoicePlayback", () => {
  it("unlocks the voice context on the first user gesture", () => {
    const spy = vi.spyOn(voicePlayer, "unlock").mockImplementation(() => {});
    renderHook(() => useVoicePlayback());
    expect(spy).not.toHaveBeenCalled(); // nothing before a gesture
    window.dispatchEvent(new Event("click"));
    expect(spy).toHaveBeenCalledTimes(1);
    // de-dupes: a second gesture does not re-unlock
    window.dispatchEvent(new Event("keydown"));
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });

  it("removes its listeners on unmount", () => {
    const spy = vi.spyOn(voicePlayer, "unlock").mockImplementation(() => {});
    const { unmount } = renderHook(() => useVoicePlayback());
    unmount();
    window.dispatchEvent(new Event("click"));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
