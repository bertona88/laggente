import { describe, expect, it, vi } from "vitest";
import { createClientMessageAttemptTracker } from "@/lib/client-message-id";

describe("client message attempt ids", () => {
  it("reuses an id after failure and rotates it after edits or success", () => {
    const makeId = vi.fn()
      .mockReturnValueOnce("attempt-1")
      .mockReturnValueOnce("attempt-2")
      .mockReturnValueOnce("attempt-3");
    const tracker = createClientMessageAttemptTracker(makeId);
    expect(tracker.idFor("  Ciao  ", "photo-1")).toBe("attempt-1");
    expect(tracker.idFor("Ciao", "photo-1")).toBe("attempt-1");
    tracker.invalidate();
    expect(tracker.idFor("Ciao corretto", "photo-1")).toBe("attempt-2");
    tracker.complete("attempt-2");
    expect(tracker.idFor("Ciao corretto", "photo-1")).toBe("attempt-3");
  });
});
