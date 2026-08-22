type RecorderForCleanup = Pick<MediaRecorder, "state" | "stop" | "ondataavailable" | "onstop">;
type StreamForCleanup = Pick<MediaStream, "getTracks">;

export interface MediaCaptureRequestGate {
  busy: boolean;
}

export function tryBeginMediaCaptureRequest(gate: MediaCaptureRequestGate): boolean {
  if (gate.busy) return false;
  gate.busy = true;
  return true;
}

export function finishMediaCaptureRequest(gate: MediaCaptureRequestGate): void {
  gate.busy = false;
}

export function shouldDisableMicrophoneControl({
  recording,
  requesting,
  sending,
  uploading,
  hasPendingAttachment,
}: {
  recording: boolean;
  requesting: boolean;
  sending: boolean;
  uploading: boolean;
  hasPendingAttachment: boolean;
}): boolean {
  if (recording) return false;
  return requesting || sending || uploading || hasPendingAttachment;
}

export function releaseMediaCapture(
  recorder: RecorderForCleanup | null,
  stream: StreamForCleanup | null,
): void {
  if (recorder) {
    recorder.ondataavailable = null;
    recorder.onstop = null;
    if (recorder.state !== "inactive") recorder.stop();
  }
  stream?.getTracks().forEach((track) => track.stop());
}

export function acceptResolvedMediaStream(
  stream: StreamForCleanup,
  disposed: boolean,
): boolean {
  if (!disposed) return true;
  releaseMediaCapture(null, stream);
  return false;
}
