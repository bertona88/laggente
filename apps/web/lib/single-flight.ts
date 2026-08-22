export interface SingleFlight<T> {
  run(factory: () => Promise<T>): Promise<T>;
}

export function createSingleFlight<T>(): SingleFlight<T> {
  let inFlight: Promise<T> | null = null;
  return {
    run(factory) {
      if (inFlight) return inFlight;
      const pending = factory();
      inFlight = pending;
      pending.finally(() => {
        if (inFlight === pending) inFlight = null;
      }).catch(() => undefined);
      return pending;
    },
  };
}
