import { afterEach, describe, expect, it, vi } from "vitest";
import { startVisiblePolling } from "@/lib/visible-polling";

afterEach(() => {
  vi.useRealTimers();
});

describe("visibility-aware polling", () => {
  it("polls only while visible, refreshes on return, and cleans up", async () => {
    vi.useFakeTimers();
    let visibility: DocumentVisibilityState = "hidden";
    const listeners = new Set<EventListener>();
    const fakeDocument = {
      get visibilityState() { return visibility; },
      addEventListener: (_name: string, listener: EventListenerOrEventListenerObject) => {
        listeners.add(listener as EventListener);
      },
      removeEventListener: (_name: string, listener: EventListenerOrEventListenerObject) => {
        listeners.delete(listener as EventListener);
      },
    } as unknown as Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
    const poll = vi.fn();
    const stop = startVisiblePolling(poll, { intervalMs: 1_000, document: fakeDocument });

    await vi.advanceTimersByTimeAsync(3_000);
    expect(poll).not.toHaveBeenCalled();
    visibility = "visible";
    listeners.forEach((listener) => listener(new Event("visibilitychange")));
    await Promise.resolve();
    expect(poll).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(poll).toHaveBeenCalledTimes(2);

    stop();
    await vi.advanceTimersByTimeAsync(2_000);
    expect(poll).toHaveBeenCalledTimes(2);
    expect(listeners).toHaveLength(0);
  });
});
