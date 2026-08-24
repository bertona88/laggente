import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { LoginForm } from "@/components/login-form";

describe("magic-link recovery", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  it("clears an invalid fragment and reloads the configured auth mode", async () => {
    window.history.replaceState(null, "", "/login?from=email#token=expired");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Il link non è più valido." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ mode: "magic_link" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));

    render(<Router><LoginForm /></Router>);

    expect(await screen.findByText("Il link non è più valido.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entra o crea il tuo spazio" })).toBeInTheDocument();
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?from=email");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/auth/magic-link/consume",
      "/api/v1/auth/mode",
    ]);
  });

  it("presents email-first open signup and shows the API's truthful delivery guidance", async () => {
    const guidance = "Abbiamo inviato un link per entrare o creare il tuo Studio. Controlla anche la cartella Spam.";
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ mode: "pilot_password" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: true, message: guidance }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));

    render(<Router><LoginForm /></Router>);

    fireEvent.change(await screen.findByRole("textbox", { name: "Email professionale" }), {
      target: { value: "persona@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entra o crea il tuo spazio" }));

    expect(await screen.findByRole("heading", { name: "Controlla la posta" })).toBeInTheDocument();
    expect(screen.getByText(/Abbiamo inviato/)).toHaveTextContent(guidance);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("consumes an open-signup fragment before entering Studio", async () => {
    window.history.replaceState(null, "", "/login#signup=verified-signup-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ authenticated: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    render(<Router><LoginForm /></Router>);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/signup/consume");
    expect(window.location.hash).toBe("");
  });
});
