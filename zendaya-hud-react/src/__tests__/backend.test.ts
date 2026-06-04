import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChat, backendHttpOrigin } from "../api/backend";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("backendHttpOrigin", () => {
  it("derives an http origin (default)", () => {
    expect(backendHttpOrigin()).toBe("http://127.0.0.1:7475");
  });
});

describe("sendChat", () => {
  it("POSTs the message as JSON to /chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);

    await sendChat("hello zendaya");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/chat");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ message: "hello zendaya" });
  });

  it("rejects on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(sendChat("x")).rejects.toThrow(/500/);
  });

  it("rejects when fetch itself throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    await expect(sendChat("x")).rejects.toThrow(/network down/);
  });
});
