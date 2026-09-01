# LAGGENTE

## Profession-agnostic product blueprint 0.5

**Status:** Current MVP blueprint
**Date:** 2026-08-24
**Supersedes:** Profession-agnostic product blueprint 0.4

---

## 1. The idea

> **LAGGENTE is where la gente meets l'agente.**

Every human professional receives a personal digital space with two conversational assistants:

1. a private Studio assistant that helps the professional shape the space by talking;
2. a public assistant that talks with people on the professional's behalf without impersonating the professional.

The two assistants share one persistent application space containing configuration, knowledge, conversations, messages, files, memory, permissions, and human participation.

```text
human professional
             ↕
private Studio assistant
             ↕
shared persistent LAGGENTE space
             ↕
public assistant
             ↕
visitor
```

There is no third coordinating AI agent. The middle is the product itself: ordinary application code and persistent data.

The foundation is profession-agnostic. For a new space, the Studio begins with “Che lavoro fai?” and specializes from the answer. Backend-owned weights make real estate the first and most prominent commercial vertical without making it the universal product identity.

---

## 2. Why this product exists

Much professional work already begins in conversations: telephone calls, voice notes, introductions, questions, photographs or documents, domain knowledge, timing, uncertainty, and trust. Real estate is the first concrete instance, not the only instance.

Existing software often asks the professional to translate those conversations into administrative records. LAGGENTE reverses that relationship. The conversation remains primary; the system remembers, organizes, and makes useful interpretations without turning the professional into a data-entry operator.

The professional gains:

- an available public presence that feels like their own space;
- continuity when they are driving, visiting properties, or unavailable;
- persistent context before entering a conversation;
- less repetitive intake work;
- a way to shape the digital experience by speaking naturally;
- help noticing where human attention may create value.

The visitor gains:

- an immediate, low-pressure conversation;
- clarity that they are speaking with an AI assistant;
- continuity across messages and supported media;
- freedom from a rigid questionnaire;
- a direct path to the named human professional;
- less repetition when the professional joins.

---

## 3. What the product is—and is not

LAGGENTE does contain two chatbot-like experiences. The value is not pretending otherwise. The value is that they act on the same living professional space.

LAGGENTE is not:

- a chatbot widget attached to a brochure site;
- Salesforce with generated messages;
- a pipeline the professional must maintain;
- a fixed qualification form disguised as conversation;
- an autonomous replacement for professional judgment;
- an accidental swarm of specialist agents.

LAGGENTE is:

- a conversational way to configure a professional digital space;
- a persistent public place where people can return;
- a shared memory between the public assistant and the professional;
- a system that derives useful, correctable views from conversations;
- a place where the professional and AI can participate visibly in the same thread.

---

## 4. The private Studio

Indicative URL: `app.laggente.com`

The Studio is the first product experience. The professional signs in, creates their professional identity, chooses an available username that becomes their public subdomain, and shapes the public space through conversation rather than a settings maze.

Entry is open and email-first. A new professional requests a short-lived, single-use verification
link; no tenant exists until the recipient proves control of the address by consuming it. LAGGENTE
then creates an isolated private Studio and inactive placeholder space. A returning professional
uses the same form to receive an ordinary login link. Members with explicit platform invitation
permission may still send curated invitations, but that permission does not propagate and is no
longer required to start. No new space resolves publicly until its professional claims a slug and
activates a first revision.

When the work is not yet known, the Studio begins with “Che lavoro fai?”. It then asks useful questions about the professional's context, territory, work, style, knowledge, preferences, and desired visitor experience. It follows the conversation rather than forcing every professional through the same onboarding fields or order.

Mauro can say in Italian:

> “Lavoro soprattutto a Roma Nord. Voglio essere diretto, ma mai aggressivo.”

> “Quando qualcuno parla di vendere una casa ereditata, ricordami di verificare se ci sono altri proprietari.”

> “Non parlare di percentuali di commissione. Dì che preferisco discuterne personalmente.”

> “La mia pagina deve sembrare più personale. Metti la mia foto più in evidenza e accorcia il messaggio iniziale.”

The Studio interprets the request and uses authorized capabilities to prepare a proposed change. It shows Mauro what it understood and what the visitor would experience. Mauro decides when the revision becomes active.

The Studio can shape, within platform-provided capabilities:

- identity and public presentation;
- tone, languages, and conversational preferences;
- approved knowledge and source material;
- topics, patterns, or situations worth noticing;
- available actions and supported media;
- when and how the professional would like to be invited;
- bounded page structure, components, and visual choices;
- starter templates and their guidance.

The Studio also has a private source library for PDF, DOCX, text, Markdown, and CSV. Its assistant
can list and inspect every source owned by that tenant. Upload is not publication: making a source
available to the public assistant produces an ordinary configuration draft and still requires
explicit professional activation. Extracted file content is treated as quoted, untrusted data.

The Studio does not impose its own real-estate doctrine. It may point out ambiguity, risk, or uncertainty, but its job is to help the professional express their intent safely and visibly.

When the professional explicitly asks, Studio can search public web sources for current facts,
including the professional's own website and public professional profiles. Search never starts
automatically during onboarding. Queries use only the minimum public identifiers needed; private
Studio material, visitor data, email bodies, credentials, and secrets stay out of them. Results are
untrusted external evidence with visible source links, not verified identity or configuration. The
professional confirms any useful finding before Studio can place it into a draft revision.

What the Studio learns becomes an evolving, document-shaped space configuration. The product keeps stable types for ownership, activation, permissions, capabilities, and safety, but it does not constrain the professional's identity or way of working to a narrow profile schema. New meaning can be represented as the conversation evolves, remains inspectable, and can be corrected.

The configuration is not just an opaque prompt written by one model for another. The application can compose runtime instructions from it while preserving the underlying professional meaning, revision history, and public preview.

It cannot change immutable platform identity, tenant isolation, safety, privacy, permissions, or authorship rules. It cannot generate arbitrary tenant code, scripts, or HTML in the MVP.

Within an enabled platform email capability, Mauro may also ask Studio to prepare professional
correspondence. Studio can seal a new exact draft or inspect tenant-owned correspondence, but it
cannot send. The product shows the draft as a read-only document inside the Studio conversation;
only Mauro's explicit authorization can hand those stored bytes to the delivery provider. A
change request is another Studio message and produces another sealed version rather than editing
the artifact in place. Incoming email is quoted, untrusted material and never an instruction to
the assistant or an automatic-reply trigger.

When the separately gated outreach capability is enabled, Studio may turn explicit public-web
research into a maximum-five candidate pack for sharing a LAGGENTE link. Sources nominate; they do
not authorize. Candidates remain research-only until the professional records exact consent or the
narrow existing-customer/similar-service basis. Studio can then seal one immutable email per
recipient. The application adds privacy and opaque-token unsubscribe links, checks suppression, and lets
the professional authorize only the complete exact bundle. The bundle describes one action and
never becomes a lead pipeline.

---

## 5. The public space

Pilot URL: `mauro.laggente.com`

The public page is the active expression of what the professional created in the Studio, not a separate generic chatbot or a landing page with a floating support widget.

It displays:

- the professional's name, portrait, agency, territory, and human role;
- a clear label identifying the public assistant as AI;
- a persistent conversation;
- text, voice-note, limited photograph, and document input;
- a conversation-scoped document room shared with the professional;
- useful interactive elements when the conversation benefits from them;
- an obvious way for the professional to participate;
- visible authorship for every AI, visitor, human, and system message.

The visitor does not need an account to begin. The application gives the visitor a secure continuation identity for that conversation. Contact details may emerge naturally later; they are not a prerequisite for being received.

The first message clearly says, in Italian, that LAGGENTE is Mauro's AI assistant. The product does not hide AI identity in legal copy or rely on color alone.

---

## 6. Natural conversation, not a hidden form

The public assistant follows the person's intent. It can ask a useful question, answer from approved active knowledge, acknowledge uncertainty, accept a voice note, photograph, or document, inspect a document shared only in its current conversation, surface what it understood, or invite Mauro.

It should not dump a questionnaire, insist on completing a field set, or force every person through the same sequence.

The assistant may progressively notice information about a property, the people involved, timing, motivations, expectations, or the desired next step. That information becomes correctable memory linked to its conversational source. Missing information is not automatically a failure.

If the assistant does not know something, it says so. It does not invent valuations, availability, appointments, conditions, credentials, legal conclusions, or professional commitments.

---

## 7. Persistent conversation and memory

Conversation is the primary record. Messages retain their actual author and are not rewritten when the system's interpretation changes.

LAGGENTE may derive:

- concise summaries;
- remembered facts and preferences;
- open questions;
- possible contradictions;
- signals that the professional may want to notice;
- suggested next actions;
- an explanation of why a conversation may deserve attention.

Derived memory is not hidden model state. It is inspectable, provenance-linked, and correctable. Correcting memory does not falsify the original transcript.

An opportunity is initially a view over a conversation, not a mandatory database object with a universal lifecycle. If LAGGENTE thinks Mauro's attention could matter, it explains why. Mauro does not have to maintain a sales stage for the system.

The Studio also offers a graph over these primary and derived materials. Mauro sits at the center;
each person is reached through an existing conversation; correctable sets connect people when a
backend-configured pattern appears in their conversations or active memory. He can find a node,
recenter the view, follow a highlighted connected path, and reopen the source conversation. This is
navigation through context, not a lead table disguised as nodes.

---

## 8. The first weighted vertical: real estate

The backend ranks real estate first for the pilot. When the professional identifies as a real-estate agent, the Studio can start from a practical template for conversations with people who may be thinking about selling a property.

The template gives the assistant useful orientation:

- understand why the person came;
- be helpful without applying pressure;
- notice relevant context naturally;
- use only Mauro's active knowledge and platform-approved material;
- make uncertainty visible;
- keep human participation easy;
- recognize when a professional valuation may be a useful next conversation.

Possible topics include the property, area, ownership, motivation, timing, condition, occupancy, expectations, contact preference, and interest in a valuation. They are not required fields or ordered steps.

Mauro can change this template through the Studio. Another professional can begin from it and shape a substantially different space without receiving a separate deployment.

Future templates may help with buyers, rentals, visits, follow-up and valuation preparation, or with evidence-backed needs in other professions. Templates are accelerators, not the permanent operating language of every professional.

---

## 9. Human participation

The professional can enter a public conversation at any appropriate moment. The product does not require a one-way handoff ceremony before a human may speak.

When Mauro writes:

- the message is visibly authored by Mauro;
- a system event may announce his arrival;
- automatic AI replies pause by default;
- the existing thread and memory remain intact.

Mauro may explicitly re-enable the assistant later. Human presence and automatic-response control are separate facts, not one overloaded pipeline status.

The AI owns continuity and organization. The human owns responsibility and judgment.

---

## 10. Activating changes without ceremony

The Studio conversation is not itself the public configuration. A casual remark must not silently alter what visitors experience.

The minimum change loop is:

> **Propose → Preview → Activate**

The Studio prepares a revision, shows its practical effect, and waits for explicit professional activation. Previous revisions remain recoverable.

Activation switches application data. It does not deploy code, create infrastructure, or change DNS for each professional.

This is a safety and authorship boundary, not a CRM workflow.

---

## 11. Agentic behavior and platform controls

The assistants may:

- reason about the current conversation;
- select among authorized tools;
- adapt language and pacing;
- propose configuration changes;
- generate correctable memory and views;
- surface uncertainty;
- decide when asking, answering, waiting, or inviting the human is useful.

The application, not the model, determines:

- account and space ownership;
- who is authenticated;
- which revision is publicly active;
- which files a participant may access;
- whether automatic replies are enabled;
- whether a tool call is authorized;
- whether an exact email artifact has human authorization to be delivered;
- whether every outreach recipient has a permitted contact basis and is absent from suppression;
- retention and deletion execution;
- immutable disclosure and safety rules.

The design goal is not maximum autonomy. It is useful agency inside trustworthy boundaries.

The public assistant has no web-search tool. It answers from the active, professionally approved
configuration and does not perform open-web research for visitors.

---

## 12. Technical architecture

The accepted MVP topology is:

- a **bespoke Vite/React single-page interface** for the brand surface, Studio, conversation workspace, and public spaces, compiled to static assets during the gateway image build;
- **same-origin REST** under `/api/v1` for conversations, configuration, authentication, attachments, and application actions;
- **FastAPI/Python and the OpenAI Agents SDK** for application logic, authorized tools, interpretation, and exactly two assistant roles;
- a hosted, read-only **web-search tool available only to the private Studio**, with cited results
  persisted in the Studio transcript; the public assistant has no corresponding tool;
- **PostgreSQL** for multi-tenant configuration, conversations, messages, memory, and events;
- **private filesystem storage** on the Hetzner server for MVP uploads;
- optional **email delivery** for signed Studio magic links when that authentication mode is configured;
- optional **Resend pilot transport** for human-authorized professional email and signed inbound
  receiving events, behind a replaceable boundary that retains Amazon SES as the planned later
  raw-message transport;
- **Docker Compose** on the existing Hetzner server;
- **wildcard DNS and TLS** for `*.laggente.com`;
- a public **backend positioning contract** for the opening Studio question and ordered, weighted vertical examples;
- an authenticated, bounded **relationship graph projection** over tenant-owned conversations and correctable memory;
- an optional, tenant-scoped **Google Calendar capability** for free/busy lookup and confirmed event
  creation after an exact visitor selection, without exposing private event details.

The production web runtime is the existing internal nginx gateway. It serves the immutable Vite
build with an SPA history fallback and proxies `/api/v1` to FastAPI; there is no separate Node.js
application server or per-tenant frontend process. Hostname routing still selects the public space,
while FastAPI remains authoritative for tenant resolution and every protected operation.

Conversation turns currently use durable, non-streaming request/response transport. The browser
does not call OpenAI directly: FastAPI selects the private Studio assistant or public assistant,
runs it through the Agents SDK, and persists the authored result before returning it. See the
[Agents SDK](https://developers.openai.com/api/docs/guides/agents) and
[ADR-0001](../decisions/0001-single-hetzner-server.md).

The FastAPI service implements the application-owned conversation and file boundary. It passes
authenticated or anonymous server context into every operation and applies tenant authorization
independently of model behavior. ChatKit transport, widgets, and store/file-store contracts are
not part of the implemented pilot; a later transport change must reuse this durable truth rather
than mirror it into another chat system.

---

## 13. Conceptual persistent model

The MVP begins with a compact persistent model:

| Concept | Responsibility |
| --- | --- |
| Account | Tenant boundary |
| Member | Authenticated professional access and permissions |
| Space | Public identity, slug, visibility, and active configuration |
| Configuration revision | Proposed, active, and recoverable space behavior |
| Participant | Visitor, professional, AI identity, or system identity in a thread |
| Conversation | Persistent private Studio or public thread |
| Message | Immutable authored conversational item |
| Attachment | Private supported media and metadata |
| Document | Private Studio source or message-bound conversation file with bounded extracted text |
| Professional email | Sealed inbound or outbound correspondence plus delivery state |
| Outreach campaign | Bounded sourced candidate pack and exact bundle-authorization state |
| Outreach recipient | Campaign-local source, contact basis, sealed artifact link, and suppression state |
| Memory item | Correctable interpretation linked to source messages |
| Event | Auditable configuration, tool, consent, speaker-control, and deletion action |
| Calendar connection | Encrypted tenant authorization plus the professional's explicit bookable-hours policy |
| Calendar booking | Idempotent provider confirmation linked to its originating conversation |

Do not create a table for every possible interpretation. Summaries, signals, and possible opportunities may begin as typed memory items or generated views. Add independent lifecycles only after real product behavior requires them.

In the implemented pilot, participant identity and visible authorship are carried by conversation
state and immutable message fields rather than a separate participant table. The schema also has
a `magic_links` support record for the optional email authentication mode, a
`professional_emails` record for immutable correspondence artifacts, and bounded outreach
campaign/recipient records when that capability is explicitly enabled. These storage choices
do not change the conceptual roles above.

Every tenant-owned record contains `account_id`. Public records also bind to the resolved professional space. The hostname selects context but never substitutes for server-side authorization.

---

## 14. Audio, photographs, and documents

Voice notes belong in the first credible product because Italian professional work, especially the first real-estate vertical, already happens through audio messages.

The MVP uses one reasoning path:

1. record or select a voice note;
2. upload it privately;
3. transcribe it on the server;
4. show editable text;
5. submit the corrected text into the same conversation;
6. persist and return the assistant's complete response through the current request/response path.

Raw audio is deleted after transcription by default unless an explicit retained-audio policy applies.

Photographs are private attachments to a conversation. The MVP limits file types, size, and count; serves them through stable same-origin endpoints that authorize every request from the current visitor or professional session; and never presents an image-derived claim as certain professional judgment. When a photograph is attached to an AI-assisted turn, its verified bytes are processed by the configured AI provider for that turn only, as disclosed in the versioned visitor privacy notice; the private attachment URL is not shared and historical photographs are not replayed on later text turns.

Documents follow two bounded lifecycles. Studio sources remain private to the professional and
private assistant until an active configuration references them. Conversation documents are
uploaded by the visitor or professional, bound to an authored message, and readable only inside
that tenant/space/conversation authorization boundary. Unbound conversation drafts expire after
one hour. Deleting a conversation deletes its document rows, extracted text, files, and scoped
events. This shared room does not implement signatures, checklists, transaction stages, or a
property dossier.

---

## 15. Italian-first experience

The default product locale is `it-IT` from the first implementation commit.

This includes:

- interface copy;
- onboarding and seeded Studio conversations;
- public assistant behavior;
- sample professional knowledge;
- emails and system messages;
- dates, times, addresses, and telephone presentation;
- product acceptance tests.

Code identifiers and technical documentation may remain in English. In code, use `professional` for the human professional and explicit names such as `studio_assistant` and `public_assistant` for AI roles.

---

## 16. Trust and privacy

The product visibly distinguishes:

- `LAGGENTE — assistente AI di Mauro`;
- `Mauro Rossi — agente immobiliare`;
- the visitor;
- system events.

The visitor must know from the first interaction that the public assistant is AI. The professional cannot configure that disclosure away.

The MVP also requires:

- clear privacy information before unnecessary personal data or files are collected;
- separate marketing consent where applicable;
- configurable retention and executable deletion paths;
- access control for conversations and files;
- explicit configuration activation before a private Studio source becomes public-assistant knowledge;
- recorded consent and speaker-control events;
- product-specific legal and privacy review before public launch.

Public web content is treated as untrusted input. Studio must not follow instructions found in a
page or use a page to authorize another tool, and it must distinguish a plausible identity match
from a professional-confirmed one. Search queries exclude private Studio, visitor, and email
content. Citations remain visible and clickable in the private transcript.

This blueprint is a product specification, not legal advice.

---

## 17. The experience we are building

The product begins on the professional side and becomes real through the public side:

1. Mauro remains the seeded first tenant and signs in through the configured secure pilot method.
2. Giulia enters her email address and LAGGENTE sends a signed, single-use verification link without creating a tenant.
3. Giulia opens the link; only then does LAGGENTE create her separate account, member, private Studio thread, and inactive space.
4. Giulia opens the link and says naturally: “Sono Giulia Bianchi, lavoro principalmente a Milano Porta Romana…”
5. The Italian Studio turns that conversation into an extensible first draft without reducing Giulia to a fixed form or publishing anything silently.
6. Giulia chooses the available username `giulia`, reserving `giulia.laggente.com` globally.
7. She reviews the concrete public effect, corrects the Studio if needed, and explicitly activates the revision.
8. The first activation makes the dormant space public. It changes PostgreSQL state; it does not deploy code, create infrastructure, or load a Giulia-specific environment file.
9. `giulia.laggente.com` now uses the same public assistant, seller template, conversation persistence, voice-note, photograph, document-sharing, memory, and human-control machinery as Mauro's space, scoped to Giulia's `account_id` and active configuration.
10. A visitor starts a natural, persistent Italian conversation without creating an account.
11. The resulting conversation and derived, correctable context are privately available only to Giulia's account.
12. Giulia can join the same thread as a visible human; automatic AI replies pause when she writes and can be explicitly re-enabled.
13. Giulia returns through the same email form and receives an ordinary magic-link login.

The experience is successful when these facts are obvious without a technical explanation:

- a new professional verified an email and created a genuinely separate space by talking;
- the public assistant changed because that professional activated a configuration revision;
- Giulia's configuration could express what mattered without becoming a rigid professional profile;
- `giulia.laggente.com` required no Giulia-specific code, deployment, DNS record, or application configuration;
- the visitor had a natural, persistent conversation;
- the system organized context without demanding CRM work;
- Giulia entered the same conversation as a visible human;
- Mauro could not read or operate Giulia's tenant-owned conversation.

---

## 18. Pilot evidence

The pilot should observe behavior without forcing a premature pipeline.

Useful evidence includes:

- professionals who repeatedly share their public link;
- visitors who return to an existing conversation;
- conversations professionals judge useful;
- generated memory that professionals or visitors correct;
- situations where system suggestions cause useful human attention;
- time from a meaningful visitor message to a professional response;
- valuation conversations and appointments that originated in LAGGENTE;
- configuration changes professionals make through the Studio;
- moments where the starting seller template helps or gets in the way.

The initial commercial signal remains qualified valuation appointments per professional per week, but the product must not encode that metric as a compulsory user workflow.

---

## 19. What this product is not trying to be

- billing and paid checkout;
- native WhatsApp integration;
- property portals and search;
- automated valuation presented as certainty;
- full CRM and configurable sales pipelines;
- rigid lead taxonomies;
- calendar aggregation, rescheduling, cancellation, or providers beyond the accepted first Google Calendar capability;
- renovation rendering;
- transaction-document orchestration;
- cross-professional network behavior;
- address-book import, bulk scraping, purchased contact lists, inferred cold-email permission, or cross-account relationship clustering;
- customer-provided code or OpenAI keys;
- property passports, blockchain proofs, crypto, payments, or title transfer;
- multi-agent swarms;
- infrastructure per professional subdomain.

These may become useful later. They do not define the product now.

---

## 20. How to implement the product

Implementation must preserve the simple product shape:

> two assistants around one persistent professional space.

Begin with the professional-facing Studio and connect it immediately to the public assistant that proves the active configuration. Do not build an isolated generic chatbot, and do not build a generic prompt platform with no public behavior to validate it. Do not scaffold future CRM concepts, speculative tables, integration placeholders, or agent roles.

For every implementation task:

- state the user-visible result;
- use Italian product fixtures and acceptance scenarios;
- allow the professional's configuration to remain document-shaped and extensible inside typed platform controls;
- keep configuration activation separate from code deployment;
- authorize every tenant-owned operation server-side;
- persist real conversations and authorship;
- keep generated memory correctable and linked to its source;
- test that the public assistant reads only active configuration;
- test cross-account denial for conversations, tools, and files;
- test human authorship and AI-response pause/resume behavior;
- label seeded, simulated, and real behavior accurately;
- update the governing document when implementation reveals a different product truth.

Do not recreate the deleted deterministic funnel under different names.

---

## 21. Final conviction

LAGGENTE is not valuable because it has a chatbot, a microphone, a vertical label, or a subdomain.

It becomes valuable when a professional can shape a digital presence by speaking, when people can hold conversations that persist and accumulate useful context, and when the system helps the right human attention arrive without creating another administrative machine.

> **La gente incontra l'agente.**
