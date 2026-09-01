# ADR-0007: Tenant-Scoped Google Calendar Appointments

- **Status:** Accepted
- **Date:** 2026-09-01

## Context

The real-estate pilot is intended to produce useful conversations and appointments, but the first
MVP deliberately stopped at appointment requests or external booking links. Professionals should
not have to copy availability into LAGGENTE, and the public assistant must never invent a free slot
or claim an event exists when a provider write failed.

## Decision

Add Google Calendar as the first optional scheduling provider inside the existing application
coordination layer and public assistant. This does not add another AI role or a CRM lifecycle.

- One tenant-owned connection belongs to one professional space and is authorized by an
  authenticated member through Google OAuth.
- OAuth credentials are encrypted at rest. The API asks only for identity, free/busy, and event
  creation scopes; it never returns titles or details of existing events to visitors or models.
- The professional explicitly defines bookable days, hours, duration, interval, buffer, minimum
  notice, title, location, and whether booking is enabled.
- The public assistant may offer only slots returned by the deterministic availability capability.
  It may create an event only after the visitor explicitly selects an exact offered slot and
  supplies the name and email address needed for the invitation.
- The application rechecks availability immediately before the write, creates the provider event
  with attendee updates enabled, persists an idempotent booking record, and records an audit event.
  Only a confirmed provider response may be described as a confirmed appointment.
- Every connection, availability lookup, booking, and audit record independently enforces
  `account_id`, `space_id`, and the current conversation authorization.
- The capability is disabled by default until the Google Cloud project and production secrets are
  configured. Disconnecting LAGGENTE deletes its local authorization; existing provider events are
  left intact.

## Consequences

### Positive

- visitors can move from a natural conversation to a real appointment without a disguised form;
- professionals retain control of working hours and can pause booking immediately;
- private calendar contents never become assistant context;
- booking retries cannot create duplicate events for the same conversation, slot, and visitor;
- appointments remain evidence attached to primary conversations rather than pipeline stages.

### Negative

- Google OAuth consent, token rotation, API quotas, and provider availability become operational
  dependencies;
- the first implementation does not aggregate multiple calendars, reschedule, or cancel events;
- Google receives the visitor name and email when an appointment is created and the privacy notice
  must state that clearly;
- adding Microsoft 365 later requires a provider adapter and a separate operational authorization.

## Alternatives considered

- **Calendly link only:** remains a safe fallback but cannot let the assistant verify or create an
  appointment in the conversation.
- **Self-host Cal.com:** rejected for the pilot because it adds another application and database
  without proving a need.
- **Give the model general calendar access:** rejected because private event content and arbitrary
  mutations exceed the capability required for booking.
- **Create events before the visitor selects a slot:** rejected because model intent is not visitor
  confirmation and speculative holds would create calendar administration.
