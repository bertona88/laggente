import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LandingPage } from "@/components/landing-page";

vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  return { ...actual, useReducedMotion: () => true };
});

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("homepage product demonstration", () => {
  it("shows AI replies and human intervention without scrolling or calling an assistant", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<LandingPage />);
    const hero = screen.getByRole("region", { name: "Un assistente AI che risponde ai tuoi clienti." });
    fireEvent.click(within(hero).getByRole("button", { name: "L’AI risponde" }));
    expect(within(hero).getByText("Il tuo assistente AI")).toBeInTheDocument();
    expect(within(hero).getByRole("button", { name: "L’AI risponde" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(hero).getByRole("button", { name: "Tu intervieni" }));
    expect(within(hero).getByText("Tu · professionista")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/product/positioning", expect.anything());
    expect(screen.queryByText("Agenti immobiliari")).not.toBeInTheDocument();
  });

  it("shows all steps with reduced motion and uses the backend's market and example", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      audience: "Architetti", opening_question: "Di quali progetti ti occupi?",
      homepage: { headline: "Un assistente per il tuo studio.", description: "Lo prepari parlando." },
      featured_verticals: [{ id: "architecture", label: "Architetti", weight: 100, status: "example",
        example_answer: "Progetto case.", headline: "Architettura", description: "Progetti e ristrutturazioni.",
        conversation_example: { instruction: "Chiedi la superficie.", visitor: "Vorrei ristrutturare.", assistant: "Quanti metri quadrati?", professional: "Guardiamo insieme il progetto." },
      }],
    }), { headers: { "content-type": "application/json" } }));
    render(<LandingPage />);
    expect(await screen.findByRole("heading", { name: "Un assistente per il tuo studio." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ai clienti basta un link." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tu riprendi da ciò che si sono detti." })).toBeInTheDocument();
    expect(screen.getAllByText("Vorrei ristrutturare.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Leggi senza animazioni" })).not.toBeInTheDocument();
    expect(screen.queryByText("Agenti immobiliari")).not.toBeInTheDocument();
  });
});
