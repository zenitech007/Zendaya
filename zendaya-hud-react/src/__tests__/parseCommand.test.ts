import { describe, it, expect } from "vitest";
import { parseCommand } from "../commands/parseCommand";

describe("parseCommand", () => {
  it("returns null for empty / whitespace input", () => {
    expect(parseCommand("")).toBeNull();
    expect(parseCommand("   ")).toBeNull();
  });
  it("parses a chat line", () => {
    expect(parseCommand("  what time is it?  ")).toEqual({ kind: "chat", text: "what time is it?" });
  });
  it("parses a slash command with no args", () => {
    expect(parseCommand("/map")).toEqual({ kind: "slash", name: "map", args: [] });
  });
  it("lowercases the command name and keeps arg case", () => {
    expect(parseCommand("/Theme Iris")).toEqual({ kind: "slash", name: "theme", args: ["Iris"] });
  });
  it("splits multiple args on runs of whitespace", () => {
    expect(parseCommand("/foo  a   b")).toEqual({ kind: "slash", name: "foo", args: ["a", "b"] });
  });
  it("treats a lone slash as /help", () => {
    expect(parseCommand("/")).toEqual({ kind: "slash", name: "help", args: [] });
  });
});
