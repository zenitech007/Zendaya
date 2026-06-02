import { describe, it, expect } from "vitest";
import { selectScene } from "../scenes/SceneManager";

describe("selectScene", () => {
  it("returns idle for the default scene", () => {
    expect(selectScene({ scene: "main", activeModule: "none" })).toBe("idle");
  });
  it("returns globe when the scene is map", () => {
    expect(selectScene({ scene: "map", activeModule: "none" })).toBe("globe");
  });
  it("returns globe when the map module is active", () => {
    expect(selectScene({ scene: "main", activeModule: "map" })).toBe("globe");
  });
  it("returns idle for a non-map module", () => {
    expect(selectScene({ scene: "main", activeModule: "calculator" })).toBe("idle");
  });
});
