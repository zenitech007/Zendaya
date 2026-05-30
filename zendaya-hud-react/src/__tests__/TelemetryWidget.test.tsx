import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import TelemetryWidget from "../components/HUD/TelemetryWidget";

beforeEach(() => {
  useZendaya.setState({ telemetry: null });
});

describe("TelemetryWidget", () => {
  it("renders nothing when telemetry is null", () => {
    const { container } = render(<TelemetryWidget />);
    expect(container.firstChild).toBeNull();
  });

  it("renders CPU/MEM/mood when populated", () => {
    useZendaya.setState({
      telemetry: {
        cpu: 23.5, mem: 60, mic_level: 0, mood: "neutral",
        vision_active: false, gestures_active: false,
        hud_enabled: true, online: true,
        user_name: "", language: "english",
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<TelemetryWidget />);
    expect(screen.getByText(/CPU/)).toBeInTheDocument();
    expect(screen.getByText(/MEM/)).toBeInTheDocument();
    expect(screen.getByText(/24%/)).toBeInTheDocument();    // CPU rounded
    expect(screen.getByText(/60%/)).toBeInTheDocument();
    expect(screen.getByText(/neutral/)).toBeInTheDocument();
  });

  it("renders offline banner when online=false", () => {
    useZendaya.setState({
      telemetry: {
        cpu: 0, mem: 0, mic_level: 0, mood: "neutral",
        vision_active: false, gestures_active: false,
        hud_enabled: true, online: false,
        user_name: "", language: "english",
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<TelemetryWidget />);
    expect(screen.getByText(/offline/)).toBeInTheDocument();
  });
});
