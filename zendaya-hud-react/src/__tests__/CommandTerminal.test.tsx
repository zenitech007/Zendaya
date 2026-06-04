import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import CommandTerminal from "../components/HUD/CommandTerminal";

beforeEach(() => {
  useZendaya.setState({
    terminalOpen: false, activeThemeId: "forge", scene: "main",
    activeModule: "none", panel: "none", connected: true,
  });
  useZendaya.getState().clearTerminalLog();
});

describe("CommandTerminal", () => {
  it("renders nothing when the terminal is closed", () => {
    render(<CommandTerminal />);
    expect(screen.queryByTestId("command-input")).toBeNull();
  });

  it("renders the input when open", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<CommandTerminal />);
    expect(screen.getByTestId("command-input")).toBeTruthy();
  });

  it("renders transcript lines from the store", () => {
    useZendaya.setState({ terminalOpen: true });
    useZendaya.getState().pushTerminalLine("system", "hello from system");
    render(<CommandTerminal />);
    expect(screen.getByText("hello from system")).toBeTruthy();
  });

  it("submitting a slash command runs it and logs user + system lines", () => {
    useZendaya.setState({ terminalOpen: true });
    render(<CommandTerminal />);
    const input = screen.getByTestId("command-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "/theme iris" } });
    fireEvent.submit(input.closest("form")!);
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    const roles = useZendaya.getState().terminalLog.map((l) => l.role);
    expect(roles).toContain("user");
    expect(roles).toContain("system");
  });
});
