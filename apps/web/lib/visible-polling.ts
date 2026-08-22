export interface VisiblePollingOptions {
  intervalMs?: number;
  document?: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  setInterval?: typeof globalThis.setInterval;
  clearInterval?: typeof globalThis.clearInterval;
}

export function startVisiblePolling(
  poll: () => void | Promise<void>,
  options: VisiblePollingOptions = {},
): () => void {
  const ownerDocument = options.document || globalThis.document;
  const schedule = options.setInterval || globalThis.setInterval;
  const cancel = options.clearInterval || globalThis.clearInterval;
  const intervalMs = options.intervalMs || 5_000;
  let running = false;

  const run = () => {
    if (ownerDocument.visibilityState !== "visible" || running) return;
    running = true;
    Promise.resolve(poll()).finally(() => { running = false; });
  };
  const onVisibilityChange = () => {
    if (ownerDocument.visibilityState === "visible") run();
  };
  const timer = schedule(run, intervalMs);
  ownerDocument.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    cancel(timer);
    ownerDocument.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
