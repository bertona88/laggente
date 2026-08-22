export function isNearThreadBottom(
  metrics: Pick<HTMLElement, "scrollHeight" | "scrollTop" | "clientHeight">,
  threshold = 96,
): boolean {
  return metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight <= threshold;
}

export function shouldAutoScrollThread(
  previousLastMessageId: string | null,
  nextLastMessageId: string | null,
  nearBottom: boolean,
  force = false,
): boolean {
  if (!nextLastMessageId) return false;
  if (force) return true;
  return previousLastMessageId !== nextLastMessageId && nearBottom;
}
