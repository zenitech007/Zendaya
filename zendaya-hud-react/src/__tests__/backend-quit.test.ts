import { afterEach, describe, expect, it, vi } from "vitest";
import { quit } from "../api/backend";

afterEach(() => vi.restoreAllMocks());

describe("quit", () => {
  it("POSTs to /quit", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await quit();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/quit");
    expect(init.method).toBe("POST");
  });

  it("swallows fetch errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    await expect(quit()).resolves.toBeUndefined();
  });
});
