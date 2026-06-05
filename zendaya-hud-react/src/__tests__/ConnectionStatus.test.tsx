import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ConnectionStatus from "../components/HUD/ConnectionStatus";

beforeEach(() => useZendaya.setState({ connected: true }));

describe("ConnectionStatus", () => {
  it("renders nothing when connected", () => {
    useZendaya.setState({ connected: true });
    render(<ConnectionStatus />);
    expect(screen.queryByTestId("connection-status")).toBeNull();
  });

  it("shows 'connecting…' when disconnected", () => {
    useZendaya.setState({ connected: false });
    render(<ConnectionStatus />);
    expect(screen.getByTestId("connection-status")).toBeTruthy();
    expect(screen.getByText("connecting…")).toBeTruthy();
  });
});
