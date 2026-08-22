import { describe, expect, it, vi } from "vitest";
import {
  acceptResolvedMediaStream,
  finishMediaCaptureRequest,
  releaseMediaCapture,
  shouldDisableMicrophoneControl,
  tryBeginMediaCaptureRequest,
} from "@/lib/media-capture";

describe("voice capture cleanup", () => {
  it("admits only one microphone permission request at a time", () => {
    const gate = { busy: false };
    expect(tryBeginMediaCaptureRequest(gate)).toBe(true);
    expect(tryBeginMediaCaptureRequest(gate)).toBe(false);
    finishMediaCaptureRequest(gate);
    expect(tryBeginMediaCaptureRequest(gate)).toBe(true);
  });

  it("keeps Stop reachable during capture while blocking a new capture during other work", () => {
    expect(shouldDisableMicrophoneControl({
      recording: true,
      requesting: false,
      sending: true,
      uploading: true,
      hasPendingAttachment: true,
    })).toBe(false);
    expect(shouldDisableMicrophoneControl({
      recording: false,
      requesting: false,
      sending: false,
      uploading: true,
      hasPendingAttachment: false,
    })).toBe(true);
  });

  it("detaches callbacks, stops an active recorder, and stops every stream track", () => {
    const firstTrack = { stop: vi.fn() };
    const secondTrack = { stop: vi.fn() };
    const recorder = {
      state: "recording",
      stop: vi.fn(),
      ondataavailable: vi.fn(),
      onstop: vi.fn(),
    };
    const stream = { getTracks: () => [firstTrack, secondTrack] };

    releaseMediaCapture(
      recorder as unknown as Pick<MediaRecorder, "state" | "stop" | "ondataavailable" | "onstop">,
      stream as unknown as Pick<MediaStream, "getTracks">,
    );

    expect(recorder.ondataavailable).toBeNull();
    expect(recorder.onstop).toBeNull();
    expect(recorder.stop).toHaveBeenCalledOnce();
    expect(firstTrack.stop).toHaveBeenCalledOnce();
    expect(secondTrack.stop).toHaveBeenCalledOnce();
  });

  it("does not stop an already inactive recorder twice", () => {
    const recorder = {
      state: "inactive",
      stop: vi.fn(),
      ondataavailable: null,
      onstop: null,
    };
    releaseMediaCapture(
      recorder as unknown as Pick<MediaRecorder, "state" | "stop" | "ondataavailable" | "onstop">,
      null,
    );
    expect(recorder.stop).not.toHaveBeenCalled();
  });

  it("rejects and stops a stream whose permission resolves after unmount", () => {
    const track = { stop: vi.fn() };
    const stream = { getTracks: () => [track] };
    expect(acceptResolvedMediaStream(
      stream as unknown as Pick<MediaStream, "getTracks">,
      true,
    )).toBe(false);
    expect(track.stop).toHaveBeenCalledOnce();
  });
});
