import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import MusicPlayer from "../components/HUD/MusicPlayer";
import { useZendaya } from "../store/zendayaStore";

const NP = (over: Partial<any> = {}) => ({
  track: "A", artist: "", is_playing: true,
  progress_ms: 0, duration_ms: 0, source: "local" as const,
  streamUrl: "/music/stream/aaa", trackId: "aaa", ...over,
});

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) }));
  useZendaya.setState({ nowPlaying: null, musicCmd: null });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("MusicPlayer", () => {
  it("always renders the <audio> element", () => {
    const { getByTestId } = render(<MusicPlayer />);
    expect(getByTestId("hud-audio").tagName).toBe("AUDIO");
  });

  it("loads the backend-selected track into <audio>", async () => {
    const { getByTestId } = render(<MusicPlayer />);
    useZendaya.setState({ nowPlaying: NP() });
    await waitFor(() => {
      const a = getByTestId("hud-audio") as HTMLAudioElement;
      expect(a.getAttribute("src")).toBe("http://127.0.0.1:7475/music/stream/aaa");
    });
  });

  it("reloads when the backend selects a different trackId", async () => {
    const { getByTestId } = render(<MusicPlayer />);
    const a = getByTestId("hud-audio") as HTMLAudioElement;
    useZendaya.setState({ nowPlaying: NP() });
    await waitFor(() => expect(a.getAttribute("src")).toContain("/aaa"));
    useZendaya.setState({ nowPlaying: NP({ track: "B", streamUrl: "/music/stream/bbb", trackId: "bbb" }) });
    await waitFor(() => expect(a.getAttribute("src")).toContain("/bbb"));
  });
});
