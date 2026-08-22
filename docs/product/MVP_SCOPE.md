# MVP Scope

## Pilot

- First professional: Mauro.
- Initial cohort: five real-estate professionals.
- Default product locale: Italian (`it-IT`).
- Initial commercial context: conversations with people considering selling a property.
- Initial commercial model: free pilot.

The seller context is the first useful template. It is not a mandatory questionnaire, CRM pipeline, or permanent product ontology.

## Product shape

The MVP contains two conversational assistants around one shared persistent space:

1. the private Studio assistant talks with the authenticated professional and helps configure the space;
2. the public assistant talks with visitors using the active configuration of that space;
3. application code coordinates configuration, conversations, memory, files, permissions, and human participation.

There is no third coordinating AI agent.

## Required professional experience

1. Mauro signs in through a magic link.
2. He enters an Italian-language Studio conversation rather than a settings dashboard.
3. The Studio begins from a useful seller-oriented template and Mauro's seeded public identity.
4. Mauro can describe changes naturally: tone, presentation, knowledge, behavior, things worth noticing, available actions, and when he would like to be invited into a conversation.
5. The Studio interprets the request, proposes the change, and shows a concrete preview of its public effect.
6. Mauro explicitly makes the proposed revision active. A casual Studio message never silently changes public behavior.
7. Mauro can return to previous revisions.
8. Mauro sees persistent public conversations ordered by useful system suggestions rather than a mandatory sales pipeline.
9. For each conversation, the system may show correctable memory, a concise summary, open questions, and why Mauro's attention may be useful.
10. Mauro can enter the same conversation, write as himself, pause automatic AI replies, and later re-enable them explicitly.

## Required visitor experience

1. A visitor opens `mauro.laggente.com` without creating an account.
2. The page and assistant are Italian by default.
3. The assistant clearly identifies itself as Mauro's AI assistant in the first message and remains visibly distinct from Mauro.
4. The visitor can converse freely through streaming text, a voice note, and a limited number of property photographs.
5. The conversation does not behave like a form with a chat skin. The assistant follows the visitor's intent and uses the seller template as guidance, not as a fixed sequence.
6. The conversation and its messages persist. Reloading the page does not erase it.
7. The visitor can return through a secure continuation mechanism without being forced to create an account.
8. The assistant remembers relevant information from the thread, avoids needless repetition, and exposes important interpretations so they can be corrected.
9. The visitor can ask for Mauro at any time, but the conversation does not need to cross a formal one-way handoff state before Mauro may participate.
10. When Mauro joins, the interface clearly shows who authored each message and whether automatic AI replies are active.

## Shared space

The professional's space contains:

- public identity and presentation;
- active assistant behavior and revision history;
- approved professional knowledge;
- enabled capabilities;
- persistent conversations and messages;
- private attachments;
- correctable conversational memory;
- system-generated summaries, signals, and suggested next actions;
- participant identity and AI-response control;
- consent and audit events where required.

Conversation is primary. Memory, summaries, signals, and possible opportunities are derived views unless real product evidence later justifies independent lifecycles.

## Initial seller template

The template gives the public assistant a credible starting orientation: understand why the person came, be useful, avoid inventing facts, notice information that may matter to Mauro, and make human participation easy.

Depending on the conversation, useful topics may include:

- the person's intention and relationship to the property;
- the property or area they are discussing;
- motivation and timing;
- ownership or co-ownership;
- condition or occupancy;
- expectations and unanswered questions;
- preferred way to continue with Mauro;
- interest in a professional valuation.

These are prompts for attention, not required fields, completion gates, or a fixed order. The Studio can modify the template for each professional within platform safety boundaries.

## Included

- multi-tenant professional accounts and authenticated members;
- personal public spaces and wildcard subdomains;
- private Studio assistant and public assistant;
- Italian-first interface and behavior;
- persistent private and public conversations;
- streaming text chat;
- chained voice-note transcription with editable text;
- limited private photograph uploads;
- professional configuration with proposed, active, and recoverable revisions;
- approved knowledge;
- correctable memory and generated conversation views;
- conversation list with suggested priorities and next actions;
- email notification for relevant activity;
- human participation and explicit AI-response control;
- AI disclosure, consent events, retention controls, and audit events.

## Explicitly excluded from the first slice

- a conventional CRM or configurable sales pipeline;
- mandatory lead statuses and data-entry workflows;
- billing and public self-service signup;
- native WhatsApp bot;
- property portal feeds and property search;
- automated valuation presented as certainty;
- renovation rendering;
- transaction document orchestration;
- cross-professional network behavior;
- property passports, blockchain proofs, crypto, payments, or title transfer;
- arbitrary tenant-provided code, scripts, or HTML;
- multi-agent swarms;
- infrastructure per professional subdomain;
- customer-provided OpenAI keys.

## Definition of done

The first vertical slice is complete when:

1. Mauro signs in and uses the Studio in Italian.
2. He asks the Studio to change the public space through natural conversation.
3. He sees the proposed effect and explicitly activates it.
4. The active change appears on `mauro.laggente.com` without a code deployment.
5. A visitor starts an Italian conversation and it survives reload and return.
6. The public assistant uses Mauro's active configuration and identifies itself correctly.
7. The visitor communicates through text or a voice note and can attach a limited photograph.
8. The system produces a useful, correctable view of the conversation without forcing a questionnaire or pipeline.
9. Mauro sees the conversation and understands why it may deserve attention.
10. Mauro joins the same thread; the visitor sees that Mauro is speaking and automatic AI replies pause.
11. Mauro can explicitly re-enable the assistant without losing conversational continuity.
