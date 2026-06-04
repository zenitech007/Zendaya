import { beforeEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { act } from "react";
import { useZendaya } from "../store/zendayaStore";
import { useCommandHotkey } from "../hooks/useCommandHotkey";

function Harness() {
  useCommandHotkey();
  return null;
}

beforeEach(() => {
  useZendaya.setState({ terminalOpen: false });
});

describe("useCommandHotkey", () => {
  it("Ctrl+K toggles the terminal open then closed", () => {
    render(<Harness />);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(true);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });

  it("Escape closes an open terminal", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<Harness />);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(useZendaya.getState().terminalOpen).toBe(false);
  });
});
