import { beforeEach, describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ThemePicker from "../components/chrome/ThemePicker";
import { THEME_ORDER, THEMES } from "../themes/registry";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("ThemePicker", () => {
  it("renders one dot per theme", () => {
    const { getAllByRole } = render(<ThemePicker />);
    expect(getAllByRole("button")).toHaveLength(THEME_ORDER.length);
  });

  it("clicking a theme dot switches the active theme", () => {
    const { getByLabelText } = render(<ThemePicker />);
    fireEvent.click(getByLabelText(THEMES.iris.name));
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("marks the active theme with aria-current", () => {
    const { getByLabelText } = render(<ThemePicker />);
    expect(getByLabelText(THEMES.forge.name).getAttribute("aria-current")).toBe("true");
  });
});
