import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => {
  useZendaya.getState().clearTerminalLog();
});

describe("terminalLog", () => {
  it("starts empty", () => {
    expect(useZendaya.getState().terminalLog).toEqual([]);
  });
  it("pushTerminalLine appends a line with role/text and a unique id", () => {
    useZendaya.getState().pushTerminalLine("user", "hi");
    useZendaya.getState().pushTerminalLine("zendaya", "hello");
    const log = useZendaya.getState().terminalLog;
    expect(log).toHaveLength(2);
    expect(log[0].role).toBe("user");
    expect(log[0].text).toBe("hi");
    expect(log[1].role).toBe("zendaya");
    expect(log[0].id).not.toBe(log[1].id);
  });
  it("caps the log at 100 lines", () => {
    for (let i = 0; i < 130; i++) useZendaya.getState().pushTerminalLine("system", String(i));
    const log = useZendaya.getState().terminalLog;
    expect(log).toHaveLength(100);
    expect(log[log.length - 1].text).toBe("129");
  });
  it("clearTerminalLog empties it", () => {
    useZendaya.getState().pushTerminalLine("user", "x");
    useZendaya.getState().clearTerminalLog();
    expect(useZendaya.getState().terminalLog).toEqual([]);
  });
});
