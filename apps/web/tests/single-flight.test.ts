import { describe, expect, it, vi } from "vitest";
import { createSingleFlight } from "@/lib/single-flight";

describe("single-flight conversation creation", () => {
  it("shares one in-flight creation across concurrent upload and send callers", async () => {
    let resolve!: (value: string) => void;
    const pending = new Promise<string>((done) => { resolve = done; });
    const factory = vi.fn(() => pending);
    const flight = createSingleFlight<string>();
    const uploadConversation = flight.run(factory);
    const sendConversation = flight.run(factory);
    expect(factory).toHaveBeenCalledTimes(1);
    resolve("conversation-a");
    await expect(Promise.all([uploadConversation, sendConversation]))
      .resolves.toEqual(["conversation-a", "conversation-a"]);
  });
});
