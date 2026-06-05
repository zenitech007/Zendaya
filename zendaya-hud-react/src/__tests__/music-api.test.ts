import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchTrackList, streamUrl, postNowPlaying } from "../api/music";

afterEach(() => vi.restoreAllMocks());

describe("streamUrl", () => {
  it("builds an absolute URL from a track id", () => {
    expect(streamUrl("abc123")).toBe("http://127.0.0.1:7475/music/stream/abc123");
  });
  it("prefixes a relative stream_url with the origin", () => {
    expect(streamUrl("/music/stream/abc123")).toBe("http://127.0.0.1:7475/music/stream/abc123");
  });
});

describe("fetchTrackList", () => {
  it("returns the parsed list on success", async () => {
    const rows = [{ id: "a", title: "A", artist: "", duration_ms: 0, stream_url: "/music/stream/a" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(rows) }));
    expect(await fetchTrackList()).toEqual(rows);
  });
  it("returns [] on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await fetchTrackList()).toEqual([]);
  });
  it("returns [] when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect(await fetchTrackList()).toEqual([]);
  });
});

describe("postNowPlaying", () => {
  it("POSTs the body as JSON to /music/now", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await postNowPlaying({ track_id: "a", is_playing: true, position_ms: 1000 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/music/now");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ track_id: "a", is_playing: true, position_ms: 1000 });
  });
  it("swallows fetch errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    await expect(postNowPlaying({ track_id: "a", is_playing: true, position_ms: 0 })).resolves.toBeUndefined();
  });
});
