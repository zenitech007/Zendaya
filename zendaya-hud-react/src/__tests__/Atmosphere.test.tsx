import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import Atmosphere from "../components/Atmosphere/Atmosphere";

describe("Atmosphere", () => {
  it("renders a decorative full-viewport grain layer", () => {
    const { getByTestId } = render(<Atmosphere />);
    const el = getByTestId("atmosphere");
    expect(el.className).toContain("zen-atmosphere");
    expect(el.getAttribute("aria-hidden")).toBe("true");
  });
});
