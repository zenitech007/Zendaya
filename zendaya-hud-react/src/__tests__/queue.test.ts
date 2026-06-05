import { describe, expect, it } from "vitest";
import { nextTrack, prevTrack, type QueueTrack } from "../music/queue";

const mk = (id: string): QueueTrack => ({ id, title: id, artist: "", duration_ms: 0, stream_url: `/music/stream/${id}` });
const L = [mk("a"), mk("b"), mk("c")];

describe("nextTrack", () => {
  it("returns the following track", () => expect(nextTrack(L, "a")?.id).toBe("b"));
  it("wraps around past the last", () => expect(nextTrack(L, "c")?.id).toBe("a"));
  it("unknown current → first", () => expect(nextTrack(L, "zzz")?.id).toBe("a"));
  it("empty list → null", () => expect(nextTrack([], "a")).toBeNull());
});

describe("prevTrack", () => {
  it("returns the preceding track", () => expect(prevTrack(L, "b")?.id).toBe("a"));
  it("wraps around before the first", () => expect(prevTrack(L, "a")?.id).toBe("c"));
  it("unknown current → first", () => expect(prevTrack(L, "zzz")?.id).toBe("a"));
  it("empty list → null", () => expect(prevTrack([], "a")).toBeNull());
});
