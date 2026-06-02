import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ThemeRoot, { themeCssVars } from "../themes/ThemeRoot";
import { THEMES } from "../themes/registry";

describe("themeCssVars", () => {
  it("maps tokens to css custom properties", () => {
    const vars = themeCssVars(THEMES.iris);
    expect(vars["--zen-primary"]).toBe(THEMES.iris.primary);
    expect(vars["--zen-accent"]).toBe(THEMES.iris.accent);
    expect(vars["--zen-bg-0"]).toBe(THEMES.iris.bg[0]);
    expect(vars["--zen-bg-1"]).toBe(THEMES.iris.bg[1]);
    expect(vars["--zen-text-glow"]).toBe(THEMES.iris.textGlow);
    expect(vars["--zen-grain"]).toBe(String(THEMES.iris.grain));
  });
});

describe("ThemeRoot", () => {
  it("renders a wrapper carrying the active theme's css vars", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    const { container } = render(
      <ThemeRoot><div>child</div></ThemeRoot>
    );
    const root = container.querySelector(".zen-theme-root") as HTMLElement;
    expect(root).toBeTruthy();
    expect(root.getAttribute("data-theme")).toBe("forge");
    expect(root.style.getPropertyValue("--zen-primary")).toBe(THEMES.forge.primary);
  });

  it("reflects a theme switch", () => {
    useZendaya.setState({ activeThemeId: "iris" });
    const { container } = render(
      <ThemeRoot><div>child</div></ThemeRoot>
    );
    const root = container.querySelector(".zen-theme-root") as HTMLElement;
    expect(root.getAttribute("data-theme")).toBe("iris");
    expect(root.style.getPropertyValue("--zen-primary")).toBe(THEMES.iris.primary);
  });
});
