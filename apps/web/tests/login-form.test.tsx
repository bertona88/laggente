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
    expect(screen.getByRole("button", { name: "Ricevi il link di accesso" })).toBeInTheDocument();
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?from=email");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/auth/magic-link/consume",
      "/api/v1/auth/mode",
    ]);
  });

  it("shows the API's non-enumerating delivery guidance instead of claiming an email was sent", async () => {
    const guidance = [
      "Se l'indirizzo è autorizzato, riceverai un link di accesso.",
      "Se è il tuo primo accesso, usa il link personale dell'invito.",
      "Controlla anche la cartella Spam.",
    ].join(" ");
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

    fireEvent.click(await screen.findByRole("button", {
      name: "Accesso su invito: usa un magic link",
    }));
    fireEvent.change(screen.getByRole("textbox", { name: "Email professionale" }), {
      target: { value: "persona@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ricevi il link di accesso" }));

    expect(await screen.findByRole("heading", { name: "Richiesta ricevuta" })).toBeInTheDocument();
    expect(screen.getByText(/Se l'indirizzo è autorizzato/)).toHaveTextContent(guidance);
    expect(screen.queryByText(/Abbiamo inviato/)).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
