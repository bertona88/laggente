import { describe, expect, it } from "vitest";
import { isNearThreadBottom, shouldAutoScrollThread } from "@/lib/thread-scroll";

describe("thread auto-scroll", () => {
  it("does not move a reader on polling-only replacement or while reading history", () => {
    expect(shouldAutoScrollThread("last-1", "last-1", true)).toBe(false);
    expect(shouldAutoScrollThread("last-1", "last-2", false)).toBe(false);
    expect(shouldAutoScrollThread("last-1", "last-2", false, true)).toBe(true);
    expect(isNearThreadBottom({ scrollHeight: 1000, scrollTop: 780, clientHeight: 200 })).toBe(true);
    expect(isNearThreadBottom({ scrollHeight: 1000, scrollTop: 300, clientHeight: 200 })).toBe(false);
  });
});
