import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { LoginForm } from "@/components/login-form";

describe("magic-link recovery", () => {
  afterEach(() => {
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
});
