import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StudioCalendar } from "@/components/studio-calendar";

const connection = {
  connected: true,
  provider: "google",
  provider_email: "mauro@example.com",
  status: "connected",
  booking_enabled: false,
  timezone: "Europe/Rome",
  work_days: [0, 1, 2, 3, 4],
  day_start: "09:00",
  day_end: "18:00",
  duration_minutes: 30,
  slot_interval_minutes: 30,
  buffer_minutes: 15,
  minimum_notice_minutes: 180,
  appointment_title: "Prima conversazione",
  location: null,
  updated_at: "2026-09-01T10:00:00Z",
};

describe("Studio calendar", () => {
  afterEach(() => vi.restoreAllMocks());

  it("states the privacy boundary when provider setup is unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(
      JSON.stringify({ available: false, connection: null }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));
    render(<StudioCalendar />);
    expect(await screen.findByText("Integrazione non ancora attiva")).toBeInTheDocument();
    expect(screen.getByText(/non vengono mostrati/)).toBeInTheDocument();
  });

  it("requires a professional save before public booking becomes active", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ available: true, connection }),
        { status: 200, headers: { "content-type": "application/json" } },
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ ...connection, booking_enabled: true }),
        { status: 200, headers: { "content-type": "application/json" } },
      ));
    render(<StudioCalendar />);
    const toggle = await screen.findByRole("checkbox", { name: /Permetti all’assistente/ });
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: "Salva impostazioni" }));
    expect(await screen.findByText("Prenotazione pubblica attiva.")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/studio/calendar",
      expect.objectContaining({ method: "PATCH" }),
    ));
  });
});
