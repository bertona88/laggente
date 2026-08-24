# MVP Scope

## What we want

LAGGENTE begins with the real-estate professional creating a personal agentic space. The professional does not begin by configuring software or filling in a rigid business profile. They talk with a private Studio assistant, and the space takes shape through that conversation.

The public assistant is not a separate chatbot project. It is the public expression of the space the professional created and the place where that configuration becomes real for visitors.

The pilot begins with Mauro, expands to five real-estate professionals, and is Italian-first (`it-IT`). The initial commercial context is conversations with people considering selling a property, but that context is a useful starting template rather than a universal questionnaire, CRM pipeline, or permanent ontology.

The expansion path is controlled invitation, not public signup. A pilot member with invitation
permission can invite an email address into a new account. That account and its space remain
dormant and tenant-isolated until the recipient accepts the single-use link, teaches Studio who
they are, claims a public username, and explicitly activates a first revision.

## The professional creates their space

The professional enters LAGGENTE and:

1. receives a personal invitation and opens its single-use magic link;
2. enters a private, dormant Studio belonging to a newly created tenant;
3. talks naturally about their identity, territory, work, experience, style, personality, knowledge, preferences, boundaries, and what they want people to experience;
4. sees a first inspectable revision take shape as the Studio understands more;
5. chooses an available public username, which reserves `<username>.laggente.com` globally;
6. reviews the proposed revision and its concrete public effect;
7. explicitly activates the revision when it represents them well;
8. returns later through the same magic-link login method and operates the resulting space.

The Studio may ask useful questions, but onboarding is not a disguised form and does not require every professional to answer the same fields in the same order. The conversation can move toward what is distinctive or important for that person.

After publication, the Studio remains the primary way to evolve the space. The professional can keep talking, correct the Studio's interpretation, add knowledge, change tone or behavior, recover an earlier revision, and activate a new one without deploying code.

## A living configuration, not a cramped schema

The Studio creates an inspectable, revisable configuration of the professional's space. That configuration may contain identity, presentation, knowledge, examples, preferences, conversational guidance, things worth noticing, available capabilities, page elements, and other material that emerges from the professional's conversation.

The application must not predetermine every meaningful fact as a fixed column, profile field, or closed taxonomy. The configuration should remain document-shaped and extensible so that two professionals can express meaningfully different ways of working without requiring separate application code.

Some structure is intentionally stable because the application must enforce it deterministically:

- account and space ownership;
- public slug and activation state;
- configuration revision identity and history;
- permissions and available platform capabilities;
- immutable AI disclosure, privacy, safety, and authorship rules;
- references to approved knowledge and private files.

Inside that stable envelope, professional meaning should be allowed to evolve. Validation protects executable boundaries and data integrity; it does not reduce a person to a predefined sales record. The configuration is also not one opaque generated system prompt. Runtime instructions may be composed from the active configuration, while the underlying meaning remains visible and correctable.

## The public expression

When the professional activates a space, the personal subdomain becomes its public expression. It contains the professional's name, role, portrait, territory, selected public information, and a prominent conversation with an assistant that clearly identifies itself as AI.

The public assistant uses only the active configuration of that professional's space. A change discussed privately does not affect visitors until the professional activates it. This lets the product test the Studio's understanding through observable public behavior: what the assistant says, what it knows, how it speaks, what it notices, what it refuses to invent, and when it brings the professional closer.

A visitor can begin without creating an account, converse naturally in Italian, return to the same persistent conversation, and eventually use supported voice notes and private photographs. The assistant follows the visitor's intent rather than marching through a qualification script.

## Information returns to the professional

Public conversations are stored inside the resolved professional's account and space. They are not shared across professionals, exposed through the hostname alone, or treated as model-owned state.

The professional can see their conversations, the original authored messages, correctable memory, concise summaries, open questions, signals, and explanations of why their attention may be useful. They can enter the same conversation as themselves. Their authorship is explicit, automatic AI replies pause by default when they write, and they may explicitly re-enable the assistant later.

Conversation remains the primary record. Memory, summaries, signals, and possible opportunities are derived views unless real use proves that they need independent lifecycles. LAGGENTE should organize attention without making the professional maintain leads, stages, fields, or statuses.

## Agent-native professional correspondence

The professional can ask the private Studio assistant to prepare an email from their LAGGENTE
address. The product does not expose a general-purpose composer or conventional inbox. Studio
creates an exact, read-only draft with visible sender, recipient, subject, body, and content
fingerprint. The professional may ask for a new version through conversation or explicitly
authorize the displayed version; Studio itself cannot send it.

Replies are retained as tenant-scoped email artifacts and announced in the private Studio
conversation. External email content is untrusted data: receiving it never invokes the model,
executes a tool, authorizes a disclosure, or sends an automatic reply. The application owns
identity, persistence, human authorization, delivery state, rate limits, and provider access.
Email transport is an optional platform capability, not another AI role or a CRM record.

## The seller-oriented beginning

The starting template helps the public assistant receive someone who may be considering selling a property. It should understand why the person came, be useful without applying pressure, avoid inventing facts, notice context that may matter, and make human participation easy.

Depending on the conversation, useful topics may include the property or area, the person's relationship to it, motivation, timing, ownership, condition, occupancy, expectations, contact preference, and interest in a professional valuation. These are possibilities for attention, not required fields, completion gates, or a fixed order.

The professional can reshape or move beyond this template through the Studio. The template accelerates the beginning; it does not define every professional or every future LAGGENTE space.

## Product boundaries

LAGGENTE contains two conversational AI roles:

1. the private Studio assistant that helps the authenticated professional shape the space;
2. the public assistant that receives visitors using the active configuration.

Application code and persistent data coordinate identity, configuration, conversations, memory, files, email artifacts, permissions, activation, delivery authorization, and human participation. There is no third coordinating AI agent.

The product is not a conventional CRM, mandatory lead workflow, native WhatsApp bot, property portal, automated valuation authority, transaction platform, multi-agent swarm, or infrastructure deployment per professional. Billing, public self-service signup or purchase, uncontrolled invitation propagation, cross-professional network behavior, arbitrary tenant code, and customer-provided OpenAI keys are not part of this product now.

The experience we want is simple to recognize: a professional creates a public identity and subdomain, teaches the Studio who they are by talking, activates a space that genuinely reflects them, receives people through its public assistant, and privately understands or joins the resulting conversations without being turned into a data-entry operator.
