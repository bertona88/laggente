import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProfessionalEmailProposal } from "@/components/professional-email-proposal";
import { normalizeProfessionalEmail } from "@/lib/professional-email";
import type { ProfessionalEmail } from "@/lib/types";

const draft: ProfessionalEmail = {
  id: "mail-1",
  direction: "outbound",
  status: "draft",
  from_address: "mauro@laggente.com",
  to_address: "giulia@example.com",
  reply_to_address: "mauro+mail-1@inbound.laggente.com",
  subject: "La tua casa a Roma",
  body_text: "Ciao Giulia,\n\nti scrivo come promesso.",
  raw_sha256: "a".repeat(64),
  content_sha256: "b".repeat(64),
  created_at: "2026-08-23T10:00:00Z",
};

afterEach(cleanup);

describe("agent-native professional email", () => {
  it("normalizes only complete immutable email artifacts", () => {
    expect(normalizeProfessionalEmail(draft)?.subject).toBe("La tua casa a Roma");
    expect(normalizeProfessionalEmail({ ...draft, content_sha256: undefined })).toBeNull();
  });

  it("renders the sealed content without editable fields and exposes human authorization", () => {
    const authorize = vi.fn();
    const requestChange = vi.fn();
    render(
      <ProfessionalEmailProposal
        email={draft}
        busy={false}
        onAuthorize={authorize}
        onRequestChange={requestChange}
      />,
    );

    expect(screen.getByText("La tua casa a Roma")).toBeInTheDocument();
    expect(screen.getByText(/ti scrivo come promesso/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Autorizza e invia" }));
    fireEvent.click(screen.getByRole("button", { name: "Chiedi una modifica" }));
    expect(authorize).toHaveBeenCalledOnce();
    expect(requestChange).toHaveBeenCalledOnce();
  });

  it("never labels a captured attempt as sent", () => {
    render(
      <ProfessionalEmailProposal
        email={{ ...draft, status: "simulated", provider: "capture" }}
        busy={false}
        onAuthorize={vi.fn()}
        onRequestChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Invio simulato — niente è uscito")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Autorizza e invia" })).not.toBeInTheDocument();
  });
});
