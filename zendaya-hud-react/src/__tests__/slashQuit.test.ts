import { describe, expect, it, vi } from "vitest";

const { quitMock } = vi.hoisted(() => ({ quitMock: vi.fn() }));
vi.mock("../api/backend", () => ({ quit: quitMock }));

import { runSlash } from "../commands/slashRegistry";

describe("/quit slash command", () => {
  it("calls backend.quit and confirms", () => {
    const msg = runSlash("quit", []);
    expect(quitMock).toHaveBeenCalledTimes(1);
    expect(msg).toContain("shutting down");
  });
});
