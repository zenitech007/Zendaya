import { beforeEach, describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ChromeFrame from "../components/chrome/ChromeFrame";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("ChromeFrame", () => {
  it("renders ring chrome for forge", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    const { queryByTestId } = render(<ChromeFrame />);
    expect(queryByTestId("ring-chrome")).toBeTruthy();
    expect(queryByTestId("aperture-chrome")).toBeNull();
  });

  it("renders aperture chrome for iris", () => {
    useZendaya.setState({ activeThemeId: "iris" });
    const { queryByTestId } = render(<ChromeFrame />);
    expect(queryByTestId("aperture-chrome")).toBeTruthy();
    expect(queryByTestId("ring-chrome")).toBeNull();
  });

  it("always renders the theme picker", () => {
    const { getByLabelText } = render(<ChromeFrame />);
    expect(getByLabelText("Theme picker")).toBeTruthy();
  });
});
