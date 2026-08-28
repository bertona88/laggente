import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OutreachCampaignProposal } from "@/components/outreach-campaign-proposal";
import { normalizeOutreachCampaign } from "@/lib/outreach";
import type { OutreachCampaign } from "@/lib/types";

const campaign: OutreachCampaign = {
  id: "campaign-1",
  name: "Prime agenzie di Roma",
  landing_url: "https://laggente.com/",
  status: "research",
  recipient_cap: 5,
  recipients: [
    {
      id: "recipient-1",
      campaign_id: "campaign-1",
      name: "Giulia Bianchi",
      email: "giulia@example.com",
      source_url: "https://example.com/giulia",
      source_label: "Profilo dell’agenzia",
      permission_basis: "not_recorded",
      status: "research_only",
      retention_until: "2026-09-26T10:00:00Z",
      created_at: "2026-08-27T10:00:00Z",
      updated_at: "2026-08-27T10:00:00Z",
    },
  ],
  created_at: "2026-08-27T10:00:00Z",
  updated_at: "2026-08-27T10:00:00Z",
};

afterEach(cleanup);

describe("consent-qualified outreach campaign", () => {
  it("keeps a public-source candidate visibly blocked without permission", () => {
    const onContinue = vi.fn();
    render(
      <OutreachCampaignProposal
        campaign={campaign}
        busy={false}
        onAuthorize={vi.fn()}
        onContinue={onContinue}
      />,
    );

    expect(screen.getByText("Ricerca — invio bloccato")).toBeInTheDocument();
    expect(screen.getByText("Nessuna base di contatto registrata")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Autorizza/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continua con Studio" }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it("authorizes only the exact ready bundle", () => {
    const onAuthorize = vi.fn();
    const ready: OutreachCampaign = {
      ...campaign,
      status: "ready",
      recipients: [
        {
          ...campaign.recipients[0],
          permission_basis: "explicit_consent",
          permission_evidence: "Consenso scritto ricevuto.",
          status: "drafted",
          professional_email: {
            id: "mail-1",
            direction: "outbound",
            status: "draft",
            from_address: "mauro@laggente.com",
            to_address: "giulia@example.com",
            subject: "Uno spazio per te",
            body_text: "Ecco il link: https://laggente.com/",
            raw_sha256: "a".repeat(64),
            content_sha256: "b".repeat(64),
            created_at: "2026-08-27T10:00:00Z",
          },
        },
      ],
    };
    render(
      <OutreachCampaignProposal
        campaign={ready}
        busy={false}
        onAuthorize={onAuthorize}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Consenso esplicito dichiarato")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Autorizza 1 invio esatto" }));
    expect(onAuthorize).toHaveBeenCalledOnce();
  });

  it("rejects malformed campaign projections", () => {
    expect(normalizeOutreachCampaign({ name: "senza id" })).toBeNull();
    expect(normalizeOutreachCampaign(campaign)?.recipients[0].name).toBe("Giulia Bianchi");
  });
});
