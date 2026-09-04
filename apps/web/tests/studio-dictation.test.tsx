import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StudioWorkspace } from "@/components/studio-workspace";

class FakeMediaRecorder {
  state: RecordingState = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(_stream: MediaStream) {}

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.ondataavailable?.({
      data: new Blob([new Uint8Array([0x1a, 0x45, 0xdf, 0xa3, 0x01])], {
        type: this.mimeType,
      }),
    } as BlobEvent);
    this.onstop?.();
  }
}

const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");

describe("Studio dictation", () => {
  const stopTrack = vi.fn();

  beforeEach(() => {
    stopTrack.mockReset();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrack }],
        }),
      },
    });
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    if (originalMediaDevices) {
      Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
    } else {
      Reflect.deleteProperty(navigator, "mediaDevices");
    }
  });

  it("inserts the transcript for review and never sends it automatically", async () => {
    const requests: Array<{ path: string; init?: RequestInit }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      requests.push({ path, init });
      if (path.endsWith("/studio/space")) {
        return new Response(JSON.stringify({
          space: {
            id: "space-1",
            slug: "mauro",
            slug_claimed: true,
            onboarding_state: "published",
            is_active: true,
            professional_name: "Mauro Rossi",
            public_role: "agente immobiliare",
          },
          active_revision: null,
          latest_draft: null,
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (path.endsWith("/studio/messages")) {
        return new Response(JSON.stringify({
          conversation: { id: "studio-1" },
          messages: [],
          memory_items: [],
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (path.endsWith("/studio/dictation")) {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBeInstanceOf(FormData);
        return new Response(JSON.stringify({
          transcript: "Lavoro soprattutto a Roma Nord.",
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      throw new Error("Unexpected request: " + path);
    });

    render(<StudioWorkspace />);

    const composer = await screen.findByLabelText("Messaggio per lo Studio");
    fireEvent.change(composer, { target: { value: "Sono Mauro." } });
    const start = await screen.findByRole("button", { name: "Inizia la dettatura" });
    fireEvent.click(start);
    const stop = await screen.findByRole("button", { name: "Termina la dettatura" });
    expect(stop).toBeEnabled();
    expect(screen.getByText(/Ti ascolto/)).toBeInTheDocument();

    fireEvent.click(stop);

    await waitFor(() => {
      expect(composer).toHaveValue("Sono Mauro. Lavoro soprattutto a Roma Nord.");
    });
    expect(composer).toBeEnabled();
    expect(stopTrack).toHaveBeenCalled();
    expect(requests.some(({ path }) => path.endsWith("/studio/dictation"))).toBe(true);
    expect(
      requests.some(({ path, init }) => (
        path.endsWith("/studio/messages") && init?.method === "POST"
      )),
    ).toBe(false);
  });

  it("keeps the composer intact when microphone permission is denied", async () => {
    vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValueOnce(
      new DOMException("denied", "NotAllowedError"),
    );
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/studio/space")) {
        return new Response(JSON.stringify({
          space: {
            id: "space-1",
            slug: "mauro",
            slug_claimed: true,
            onboarding_state: "published",
            is_active: true,
          },
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (path.endsWith("/studio/messages")) {
        return new Response(JSON.stringify({ messages: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      throw new Error("Unexpected request: " + path);
    });

    render(<StudioWorkspace />);
    const composer = await screen.findByLabelText("Messaggio per lo Studio");
    fireEvent.change(composer, { target: { value: "Testo già scritto" } });
    fireEvent.click(screen.getByRole("button", { name: "Inizia la dettatura" }));

    expect(await screen.findByText(
      "Per dettare, autorizza l’accesso al microfono.",
    )).toBeInTheDocument();
    expect(composer).toHaveValue("Testo già scritto");
    expect(composer).toBeEnabled();
  });
});
