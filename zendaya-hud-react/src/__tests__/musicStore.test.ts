import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => useZendaya.setState({ musicCmd: null }));

describe("pushMusicCmd", () => {
  it("stores the command with a monotonic seq that re-fires on repeats", () => {
    useZendaya.getState().pushMusicCmd("next");
    const a = useZendaya.getState().musicCmd!;
    expect(a.cmd).toBe("next");
    useZendaya.getState().pushMusicCmd("next");
    const b = useZendaya.getState().musicCmd!;
    expect(b.cmd).toBe("next");
    expect(b.seq).toBeGreaterThan(a.seq);
  });
});
