import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { RelationshipGraph } from "@/components/relationship-graph";

const graph = {
  center_id: "professional",
  nodes: [
    { id: "professional", type: "professional", label: "Mauro", summary: "Agente immobiliare", member_count: 2, weight: 1, origin: "primary" },
    { id: "person:one", type: "person", label: "Persona 1", summary: "Una casa ereditata.", conversation_id: "one", member_count: 0, weight: 1, origin: "primary" },
    { id: "person:two", type: "person", label: "Persona 2", summary: "Vorrei una valutazione.", conversation_id: "two", member_count: 0, weight: 1, origin: "primary" },
    { id: "set:inheritance", type: "set", label: "Casa ereditata", summary: "Situazioni ereditarie.", member_count: 1, weight: 95, origin: "derived" },
  ],
  edges: [
    { id: "conversation:one", source: "professional", target: "person:one", relation: "conversation", weight: 1 },
    { id: "conversation:two", source: "professional", target: "person:two", relation: "conversation", weight: 1 },
    { id: "member:one", source: "person:one", target: "set:inheritance", relation: "member_of", weight: 95 },
  ],
  profile: { vertical_id: "real_estate_it", vertical_label: "Agenti immobiliari", template_id: "seller_it_v1", source: "backend_positioning" },
  bounds: { conversation_limit: 60, node_limit: 90, edge_limit: 180 },
};

describe("Studio relationship graph", () => {
  afterEach(() => vi.restoreAllMocks());

  it("re-centers derived sets and keeps people linked to their conversations", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(graph), { status: 200, headers: { "content-type": "application/json" } }),
    );
    render(<Router><RelationshipGraph /></Router>);

    expect(await screen.findByRole("heading", { name: "Grafo" })).toBeInTheDocument();
    expect(screen.getByText("Agenti immobiliari")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Casa ereditata/ }));
    expect(screen.getByRole("heading", { name: "Casa ereditata" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Persona, tema, situazione…"), {
      target: { value: "valutazione" },
    });
    const searchResult = screen.getAllByRole("button", { name: /Persona 2/ })
      .find((button) => !button.hasAttribute("aria-pressed"));
    expect(searchResult).toBeDefined();
    fireEvent.click(searchResult!);
    expect(screen.getByRole("link", { name: /Apri la conversazione/ })).toHaveAttribute(
      "href",
      "/studio/conversazioni/two",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/studio/relationship-graph",
      expect.objectContaining({ credentials: "include" }),
    ));
  });
});
