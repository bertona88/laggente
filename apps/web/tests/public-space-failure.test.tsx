import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { PublicSpace } from "@/components/public-space";

describe("public space failure boundary", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("does not leave a tenant placeholder interactive when resolution fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("API unavailable"));

    render(<Router><PublicSpace slug="mauro" /></Router>);

    expect(await screen.findByText("Non riesco ad aprire questo spazio.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Il tuo messaggio")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });

  it("preserves an inactive conversation so its token holder can still delete it", async () => {
    window.localStorage.setItem("laggente:conversation:mauro", "conversation-inactive");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/public/mauro")) {
        return new Response(JSON.stringify({ detail: "Spazio non trovato" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      }
      if (path.endsWith("/public/conversations/conversation-inactive")) {
        return new Response(JSON.stringify({ detail: "Spazio non attivo; la conversazione può ancora essere eliminata" }), {
          status: 410,
          headers: { "content-type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<Router><PublicSpace slug="mauro" /></Router>);

    expect(await screen.findByRole("button", { name: "Elimina la conversazione conservata" })).toBeInTheDocument();
    expect(window.localStorage.getItem("laggente:conversation:mauro")).toBe("conversation-inactive");
    expect(screen.queryByLabelText("Il tuo messaggio")).not.toBeInTheDocument();
  });

  it("switches a known conversation to the unavailable deletion surface on 410", async () => {
    window.localStorage.setItem("laggente:conversation:mauro", "conversation-closed");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/public/mauro")) {
        return new Response(JSON.stringify({
          slug: "mauro",
          professional_name: "Mauro Rossi",
          public_role: "Agente immobiliare",
          ai_label: "LAGGENTE — assistente AI di Mauro",
          privacy_notice_version: "2026-08-22",
          configuration: {
            identity: { name: "Mauro Rossi", role: "Agente immobiliare" },
            public: { welcome: "Benvenuto nello spazio di Mauro." },
            capabilities: { text: true, voice_notes: false, photographs: false },
          },
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (path.endsWith("/public/conversations/conversation-closed")) {
        return new Response(JSON.stringify({ detail: "Spazio non attivo" }), {
          status: 410,
          headers: { "content-type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<Router><PublicSpace slug="mauro" /></Router>);

    expect(await screen.findByText(
      "Questo spazio non è più disponibile. La conversazione resta conservata e può essere eliminata.",
    )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Elimina la conversazione conservata" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Il tuo messaggio")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("laggente:conversation:mauro")).toBe("conversation-closed");
  });

  it("confirms an inactive conversation deletion on the unavailable surface", async () => {
    window.localStorage.setItem("laggente:conversation:mauro", "conversation-inactive");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path.endsWith("/public/mauro")) {
        return new Response(JSON.stringify({ detail: "Spazio non trovato" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      }
      if (path.endsWith("/public/conversations/conversation-inactive") && init?.method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      if (path.endsWith("/public/conversations/conversation-inactive")) {
        return new Response(JSON.stringify({ detail: "Spazio non attivo" }), {
          status: 410,
          headers: { "content-type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<Router><PublicSpace slug="mauro" /></Router>);
    fireEvent.click(await screen.findByRole("button", { name: "Elimina la conversazione conservata" }));

    expect(await screen.findByText("La conversazione e i suoi allegati sono stati eliminati.")).toBeInTheDocument();
    expect(window.localStorage.getItem("laggente:conversation:mauro")).toBeNull();
  });

  it("reports an inactive conversation deletion failure on the unavailable surface", async () => {
    window.localStorage.setItem("laggente:conversation:mauro", "conversation-inactive");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path.endsWith("/public/mauro")) {
        return new Response(JSON.stringify({ detail: "Spazio non trovato" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      }
      if (path.endsWith("/public/conversations/conversation-inactive") && init?.method === "DELETE") {
        return new Response(JSON.stringify({ detail: "Eliminazione temporaneamente non disponibile" }), {
          status: 503,
          headers: { "content-type": "application/json" },
        });
      }
      if (path.endsWith("/public/conversations/conversation-inactive")) {
        return new Response(JSON.stringify({ detail: "Spazio non attivo" }), {
          status: 410,
          headers: { "content-type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<Router><PublicSpace slug="mauro" /></Router>);
    fireEvent.click(await screen.findByRole("button", { name: "Elimina la conversazione conservata" }));

    expect(await screen.findByText("Eliminazione temporaneamente non disponibile")).toBeInTheDocument();
    expect(window.localStorage.getItem("laggente:conversation:mauro")).toBe("conversation-inactive");
  });

  it("shows the human follow-up state after refreshing a paused conversation", async () => {
    window.localStorage.setItem("laggente:conversation:mauro", "conversation-human");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.endsWith("/public/mauro")) {
        return new Response(JSON.stringify({
          slug: "mauro",
          professional_name: "Mauro Rossi",
          public_role: "Agente immobiliare",
          territory: "Roma Nord",
          ai_label: "LAGGENTE — assistente AI di Mauro",
          privacy_notice_version: "2026-08-22",
          configuration: {
            identity: { name: "Mauro Rossi", role: "Agente immobiliare", territory: "Roma Nord" },
            public: { welcome: "Benvenuto nello spazio di Mauro." },
            capabilities: { text: true, voice_notes: false, photographs: false },
          },
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      if (path.endsWith("/public/conversations/conversation-human")) {
        return new Response(JSON.stringify({
          conversation: {
            id: "conversation-human",
            space_slug: "mauro",
            automatic_ai_enabled: false,
            professional_joined: true,
          },
          messages: [{
            id: "human-message",
            author_type: "professional",
            author_label: "Mauro Rossi",
            content: "Ti rispondo personalmente.",
            created_at: "2026-08-22T10:00:00Z",
          }],
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(<Router><PublicSpace slug="mauro" /></Router>);

    expect(await screen.findByText("Mauro risponde qui")).toBeInTheDocument();
    expect(screen.getByLabelText("Il tuo messaggio")).toHaveAttribute("placeholder", "Scrivi a Mauro…");
    expect(screen.getByText("Mauro può leggere e rispondere in questa conversazione; l’assistente AI è in pausa.")).toBeInTheDocument();
    expect(screen.queryByText("Disponibile ora")).not.toBeInTheDocument();
  });
});
