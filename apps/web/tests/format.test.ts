import { describe, expect, it } from "vitest";
import { formatDateTime, formatTime } from "@/lib/format";

describe("Italian pilot date formatting", () => {
  it("uses Europe/Rome independently from the Node or browser host timezone", () => {
    expect(formatTime("2026-01-15T12:00:00Z")).toBe("13:00");
    expect(formatTime("2026-07-15T12:00:00Z")).toBe("14:00");
    expect(formatTime("2026-07-15T12:00:00")).toBe("14:00");
    expect(formatDateTime("2026-01-15T12:00:00Z")).toContain("13:00");
  });
});
