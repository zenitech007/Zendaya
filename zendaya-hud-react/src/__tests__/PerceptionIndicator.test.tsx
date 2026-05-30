import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import PerceptionIndicator from "../components/HUD/PerceptionIndicator";

beforeEach(() => {
  useZendaya.setState({ perception: null });
});

describe("PerceptionIndicator", () => {
  it("renders nothing when perception is null", () => {
    const { container } = render(<PerceptionIndicator />);
    expect(container.firstChild).toBeNull();
  });

  it("shows 'sees you' + recent gesture", () => {
    const nowSec = Date.now() / 1000;
    useZendaya.setState({
      perception: {
        face: { present: true, ts: nowSec },
        last_gesture: { name: "Thumb_Up", ts: nowSec - 0.5 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.getByText(/sees you/)).toBeInTheDocument();
    expect(screen.getByText(/Thumb Up/)).toBeInTheDocument();
  });

  it("hides chip when gesture is stale (>3s old)", () => {
    const nowSec = Date.now() / 1000;
    useZendaya.setState({
      perception: {
        face: { present: true, ts: nowSec },
        last_gesture: { name: "Thumb_Up", ts: nowSec - 10 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.queryByText(/Thumb Up/)).toBeNull();
  });

  it("shows 'looking' when face not present", () => {
    useZendaya.setState({
      perception: {
        face: { present: false, ts: 0 },
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.getByText(/looking/)).toBeInTheDocument();
  });
});
