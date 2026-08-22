# LAGGENTE

## Agentic product blueprint 0.3

**Status:** Current MVP blueprint
**Date:** 2026-08-22
**Supersedes:** Founding draft 0.2

---

## 1. The idea

> **LAGGENTE is where la gente meets l'agente.**

Every human real-estate professional receives a personal digital space with two conversational assistants:

1. a private Studio assistant that helps the professional shape the space by talking;
2. a public assistant that talks with people on the professional's behalf without impersonating the professional.

The two assistants share one persistent application space containing configuration, knowledge, conversations, messages, files, memory, permissions, and human participation.

```text
human real-estate professional
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

---

## 2. Why this product exists

Real-estate work already begins in conversations: telephone calls, voice notes, introductions, questions, photographs, local knowledge, timing, uncertainty, and trust.

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

The Studio is where the professional shapes the public space. Its primary interface is a conversation, not a settings maze.

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

The Studio does not impose its own real-estate doctrine. It may point out ambiguity, risk, or uncertainty, but its job is to help the professional express their intent safely and visibly.

It cannot change immutable platform identity, tenant isolation, safety, privacy, permissions, or authorship rules. It cannot generate arbitrary tenant code, scripts, or HTML in the MVP.

---

## 5. The public space

Pilot URL: `mauro.laggente.com`

The public page is a personal conversational space, not a landing page with a floating support widget.

It displays:

- the professional's name, portrait, agency, territory, and human role;
- a clear label identifying the public assistant as AI;
- a persistent conversation;
- text, voice-note, and limited photograph input;
- useful interactive elements when the conversation benefits from them;
- an obvious way for the professional to participate;
- visible authorship for every AI, visitor, human, and system message.

The visitor does not need an account to begin. The application gives the visitor a secure continuation identity for that conversation. Contact details may emerge naturally later; they are not a prerequisite for being received.

The first message clearly says, in Italian, that LAGGENTE is Mauro's AI assistant. The product does not hide AI identity in legal copy or rely on color alone.

---

## 6. Natural conversation, not a hidden form

The public assistant follows the person's intent. It can ask a useful question, answer from approved knowledge, acknowledge uncertainty, accept a voice note or photograph, surface what it understood, or invite Mauro.

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

---

## 8. The first seller-oriented template

The pilot starts from a practical template for conversations with people who may be thinking about selling a property.

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

Future templates may help with buyers, rentals, visits, follow-up, valuation preparation, or other real-estate conversations. Templates are accelerators, not the permanent operating language of every professional.

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
- retention and deletion execution;
- immutable disclosure and safety rules.

The design goal is not maximum autonomy. It is useful agency inside trustworthy boundaries.

---

## 12. Technical architecture

The accepted MVP topology is:

- **Next.js/React** for the brand surface, Studio, conversation workspace, and public spaces;
- **ChatKit with a custom server integration** for streaming conversations, threads, attachments, actions, and widgets;
- **FastAPI/Python and the OpenAI Agents SDK** for the two assistant roles, tools, streaming, and interpretation;
- **PostgreSQL** for multi-tenant configuration, conversations, messages, memory, and events;
- **private filesystem storage** on the Hetzner server for MVP uploads;
- **email** for initial activity notifications;
- **Docker Compose** on the existing Hetzner server;
- **wildcard DNS and TLS** for `*.laggente.com`.

OpenAI's current guidance for new ChatKit work is the custom server-side path rather than Agent Builder-hosted workflows. See [ChatKit](https://developers.openai.com/api/docs/guides/chatkit), [advanced ChatKit integrations](https://developers.openai.com/api/docs/guides/custom-chatkit), and the [Agents SDK](https://developers.openai.com/api/docs/guides/agents).

The FastAPI service implements durable ChatKit store and file-store contracts. It passes authenticated or anonymous server context into every operation and applies tenant authorization independently of model behavior.

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
| Memory item | Correctable interpretation linked to source messages |
| Event | Auditable configuration, tool, consent, speaker-control, and deletion action |

Do not create a table for every possible interpretation. Summaries, signals, and possible opportunities may begin as typed memory items or generated views. Add independent lifecycles only after real product behavior requires them.

Every tenant-owned record contains `account_id`. Public records also bind to the resolved professional space. The hostname selects context but never substitutes for server-side authorization.

---

## 14. Audio and photographs

Voice notes belong in the first credible product because Italian real-estate work already happens through audio messages.

The MVP uses one reasoning path:

1. record or select a voice note;
2. upload it privately;
3. transcribe it on the server;
4. show editable text;
5. submit the corrected text into the same conversation;
6. stream the assistant's response.

Raw audio is deleted after transcription by default unless an explicit retained-audio policy applies.

Photographs are private attachments to a conversation. The MVP limits file types, size, and count; serves them through authorized short-lived URLs; and never presents an image-derived claim as certain professional judgment.

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

Code identifiers and technical documentation may remain in English. In code, use `professional` for the human real-estate professional and explicit names such as `studio_assistant` and `public_assistant` for AI roles.

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
- recorded consent and speaker-control events;
- product-specific legal and privacy review before public launch.

This blueprint is a product specification, not legal advice.

---

## 17. The first build

The first complete slice includes:

1. Mauro signs in through a magic link.
2. The Studio and public surfaces are Italian.
3. Mauro changes his public space by speaking naturally with the Studio.
4. The Studio shows the proposed effect and Mauro activates it.
5. The public assistant immediately uses the active revision without redeployment.
6. A visitor starts a persistent conversation without creating an account.
7. Text streams and the visitor can use a voice note and limited photograph upload.
8. The assistant uses the seller template as flexible guidance.
9. The system creates correctable memory and a useful view of the conversation.
10. Mauro sees the thread and why it may deserve attention.
11. Mauro joins the same thread and automatic AI replies pause.
12. Mauro can explicitly re-enable the assistant without losing continuity.

The demo succeeds when these facts are obvious without a technical explanation:

- Mauro shaped the space by talking;
- the public assistant changed because Mauro activated a configuration revision;
- the visitor had a natural, persistent conversation;
- the system organized context without demanding CRM work;
- Mauro entered the same conversation as a visible human.

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

## 19. Outside the first slice

- billing and public self-service signup;
- native WhatsApp integration;
- property portals and search;
- automated valuation presented as certainty;
- full CRM and configurable sales pipelines;
- rigid lead taxonomies;
- calendar automation beyond simple requests or links;
- renovation rendering;
- transaction-document orchestration;
- cross-professional network behavior;
- customer-provided code or OpenAI keys;
- property passports, blockchain proofs, crypto, payments, or title transfer;
- multi-agent swarms;
- infrastructure per professional subdomain.

These may become useful later. They do not define the product now.

---

## 20. Implementation brief

Implementation must preserve the simple product shape:

> two assistants around one persistent professional space.

Build the smallest coherent walking slice for the current milestone. Do not scaffold future CRM concepts, speculative tables, integration placeholders, or agent roles.

For every implementation task:

- state the user-visible result;
- use Italian product fixtures and acceptance scenarios;
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

LAGGENTE is not valuable because it has a chatbot, a microphone, or a subdomain.

It becomes valuable when a professional can shape a digital presence by speaking, when people can hold conversations that persist and accumulate useful context, and when the system helps the right human attention arrive without creating another administrative machine.

> **La gente incontra l'agente.**
