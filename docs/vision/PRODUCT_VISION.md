# Product Vision

## Thesis

> **LAGGENTE is where la gente meets l'agente.**

LAGGENTE gives a human professional a living digital space. The professional shapes that space by talking with a private Studio assistant. People enter the public side and speak with another assistant that knows the professional's active configuration, remembers the conversation, and can bring the professional into the same thread.

The base product is not tied to one profession. A new relationship begins with “Che lavoro fai?” and becomes specific from the professional's answer. Commercially, LAGGENTE is intentionally weighted toward Italian real-estate agents first; that priority selects the first examples and template, not the permanent identity of the product.

The product is deliberately simple to explain:

```text
professional ↔ Studio assistant ↔ shared space ↔ public assistant ↔ visitor
```

The shared space is the product. It contains the professional's identity and knowledge, active behavior, persistent conversations, messages, files, useful memory, and human participation.

The experience begins with the professional creating that space. They choose their public identity and subdomain, then teach the private Studio who they are and what the space should become through open conversation. The public assistant is the resulting space in use, not a generic visitor chatbot built before the professional side.

Professional entry is open and email-first. An unknown address receives a short-lived, single-use
verification link; LAGGENTE creates the private tenant only when the link is consumed. Existing
professionals return through the same form. No public hostname resolves until the professional
claims a slug and explicitly activates a configuration revision.

## Two conversational assistants

LAGGENTE does contain two chatbot-like interfaces. That is not something to disguise.

### Private Studio assistant

The professional explains how they work and what they want their public space to become. The Studio can propose and apply authorized changes to content, behavior, tone, presentation, memory preferences, and available capabilities. It begins from useful templates but does not impose a profession, a real-estate method, or a generic method that erases the person's actual work.

The Studio must not reduce that conversation to a closed professional-profile schema. Professional meaning remains extensible and document-shaped inside platform-owned boundaries for identity, permissions, activation, safety, and executable capabilities.

On the professional's explicit request, Studio may perform read-only research across public web
sources—for example, to find the professional's site or public professional profiles. It shows
clickable sources, preserves ambiguity between a plausible match and verified identity, and waits
for the professional's confirmation before using a finding in a proposed configuration. This
research capability remains private to Studio.

### Public assistant

The visitor speaks naturally rather than completing a disguised form. The public assistant uses the professional's active configuration, maintains continuity, works with text and supported media, and makes it easy for the professional to join. It does not search the web for visitors.

The two assistants do not talk through a third AI manager. Ordinary application code coordinates persistence, permissions, configuration, identity, and response control.

## Agentic behavior, deterministic boundaries

The product should be dynamic where intelligence helps:

- follow the shape of a real conversation;
- decide which authorized capability is useful next;
- build and revise useful memory from what people say;
- surface patterns, questions, signals, and possible next actions;
- adapt the space to the professional through conversation;
- let the professional correct or redirect the system.

The product should be deterministic where trust requires it:

- who can read or change a professional's space;
- which configuration is active publicly;
- which professional owns a conversation or file;
- whether an AI or human authored a message;
- whether automatic replies are enabled;
- what is retained or deleted;
- what the AI may never misrepresent.

Agentic does not mean arbitrary. It means the system can reason and act inside visible, authorized boundaries.

## Conversation is primary

LAGGENTE is not a conventional CRM and should not become one by accident.

The professional should not have to maintain lead records, pipeline stages, or arbitrary status fields. A conversation is the durable source. From it, LAGGENTE can derive correctable memory, summaries, signals, questions, and possible opportunities.

An opportunity is therefore not the starting point of the model. It is one useful interpretation of a conversation: the system believes the professional's attention could create value, and it can explain why.

If real usage later proves that opportunities need their own lifecycle, that lifecycle can be introduced from evidence rather than invented in advance.

## A graph for seeing relationships

The private Studio can render a bounded relationship graph over material the professional already
owns in LAGGENTE. The professional is connected to people through their public conversations; people
can also connect to derived, correctable sets such as a shared situation, subject, or territory. The
graph is a way to move through conversation context, not a declaration of who a person is.

Real estate receives the first backend-weighted set vocabulary — for example selling intent,
inheritance, valuation, shared ownership, timing, and territory. Those weights are tunable without a
frontend release. They nominate useful views; topology and weight never turn an interpretation into a
fact. Every person node resolves back to the primary conversation, and corrected or dismissed memory
changes the next graph calculation.

## The first weighted commercial vertical

The pilot starts with Mauro and conversations with people considering selling a property. Real estate is the highest-weighted vertical in backend positioning, so it remains prominent on the brand surface and receives the first deep template. LAGGENTE should help Mauro receive those people well, remember what matters, answer from approved knowledge, and participate when useful.

This initial seller template gives the space a credible starting point. It may suggest topics such as the property, motivation, timing, ownership, contact preference, and interest in a valuation. It never forces a fixed order or requires every conversation to become a dossier.

The first commercial proof remains whether the product helps professionals create more useful valuation conversations and appointments. That outcome is a learning signal, not a database ontology.

## The human and the machine

AI owns availability, continuity, organization, and repeatable assistance. The human professional owns judgment, responsibility, negotiation, physical presence, and local trust.

The professional does not receive a conversation only after a formal handoff. They can enter the same persistent thread whenever appropriate. While the human is responding, automatic AI replies can pause; when explicitly re-enabled, the assistant can participate again. Every message must identify its actual speaker.

## Italian-first product

The first real product is Italian. Interface language, seeded examples, notifications, conversational behavior, dates, addresses, and acceptance testing use `it-IT` from the beginning.

Technical documentation and code identifiers may remain in English. In code, `professional` means the human professional; avoid using the bare word `agent` when it could mean either a human role or an AI agent.

## Expansion path

1. One profession-agnostic personal space with real estate as the first weighted vertical and one strong seller-oriented starting template.
2. More real-estate configurations for buyers, rentals, visits and follow-up, alongside evidence-backed templates for other professions.
3. Connections to external systems when real work proves that they are useful.
4. A network of professional spaces that can coordinate with explicit permissions.
5. Broader professional processes in which people express intentions conversationally while named humans and institutions retain responsibility.

## Discovering the next verticals

The tenant-private graph can reveal which sets are actually useful within a professional's work. A
later, separate discovery project may analyze an explicitly authorized relationship network to find
coherent sets of professionals and decide where to invest in the next template. It must not silently
import address books, score private contacts, share tenant data, or create a hidden CRM. External
contact networks and cross-account analysis are not authorized by the MVP graph.

## Product principles

- The conversation is the primary object.
- The professional configures the space by talking, not by administering a settings maze.
- Templates accelerate the beginning; they do not dictate the business.
- Generated memory and interpretations are visible and correctable.
- The system organizes work instead of creating data-entry work.
- AI and human participation remain unmistakable.
- The personal subdomain is the professional's living space, not a landing page with a widget attached.
- Configuration activation is a product action; code deployment is an engineering action.
- The model is not the moat. The evolving relationship between professionals, people, conversations, and useful action is the moat.
