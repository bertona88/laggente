import http from "node:http";

const port = Number(process.env.LAGGENTE_VIDEO_MOCK_PORT || 8000);
const now = "2026-08-25T16:30:00Z";

let activated = false;
let joined = false;
let publicMessages = [];

const professionalMessage = {
  id: "professional-1",
  author_type: "professional",
  author_name: "Mauro Rossi",
  content: "Ho letto. Prima della valutazione verifichiamo la conformità della veranda. Se vuoi, carica qui la planimetria.",
  created_at: "2026-08-25T16:34:00Z",
};

const visitorMessage = {
  id: "visitor-1",
  author_type: "visitor",
  author_name: "Giulia",
  content: "Sto pensando di vendere un appartamento ereditato a Roma Nord. Ho la planimetria, ma non so se la veranda è conforme.",
  created_at: "2026-08-25T16:31:00Z",
};

const assistantMessage = {
  id: "assistant-1",
  author_type: "public_assistant",
  author_name: "LAGGENTE — assistente AI di Mauro Rossi",
  content: "Posso raccogliere il contesto per Mauro. La veranda risulta nella planimetria catastale oppure è stata aggiunta successivamente?",
  created_at: "2026-08-25T16:31:20Z",
};

const revision = {
  id: "revision-demo",
  number: 1,
  status: "proposed",
  title: "Accoglienza per chi sta pensando di vendere",
  summary: "Una presenza chiara e personale per le prime conversazioni su immobili a Roma Nord.",
  created_at: now,
  sections: [
    {
      key: "identity",
      title: "Identità professionale",
      value: "Mauro Rossi · agente immobiliare · Roma Nord",
      changed: true,
    },
    {
      key: "approach",
      title: "Modo di lavorare",
      value: "Prima di una valutazione controlla provenienza, conformità urbanistica e catastale, APE, occupazione e vincoli.",
      changed: true,
    },
  ],
  preview: {
    slug: "mauro",
    professional_name: "Mauro Rossi",
    professional_role: "agente immobiliare",
    agency: "Mauro Immobiliare",
    territory: "Roma Nord",
    hero_image_url: "/images/laggente-hero.webp",
    welcome_message: "Ciao, sono l'assistente AI di Mauro. Posso ascoltare ciò che stai valutando e aiutarti a capire quale potrebbe essere il prossimo passo utile.",
    assistant_disclosure: "LAGGENTE — assistente AI di Mauro Rossi",
  },
};

function session() {
  return {
    authenticated: true,
    member: {
      id: "member-mauro",
      account_id: "account-mauro",
      email: "mauro@example.test",
      display_name: "Mauro Rossi",
      role: "owner",
      can_invite: false,
    },
    space: {
      id: "space-mauro",
      account_id: "account-mauro",
      slug: "mauro",
      professional_name: "Mauro Rossi",
      agency: "Mauro Immobiliare",
      territory: "Roma Nord",
      public_role: "agente immobiliare",
      locale: "it-IT",
      is_active: activated,
      slug_claimed: true,
      // Keep the capture focused on the Studio conversation. The share-link
      // handoff is shown in its own authored transition later in the short.
      onboarding_state: "published",
      active_revision_id: activated ? revision.id : null,
    },
  };
}

function spaceBootstrap() {
  return {
    space: session().space,
    latest_draft: activated ? null : revision,
    proposed_revision: activated ? null : revision,
    active_revision: activated ? { ...revision, status: "active" } : null,
  };
}

function conversationDetail() {
  const messages = [
    visitorMessage,
    assistantMessage,
    ...(joined ? [{ id: "join-event", author_type: "system", author_name: "LAGGENTE", content: "Mauro è entrato nella conversazione. Le risposte automatiche sono in pausa.", created_at: "2026-08-25T16:33:30Z" }, professionalMessage] : []),
  ];
  return {
    conversation: {
      id: "demo-conversation",
      space_slug: "mauro",
      visitor_name: "Giulia",
      professional_present: joined,
      automatic_replies_enabled: !joined,
      created_at: "2026-08-25T16:31:00Z",
      updated_at: joined ? "2026-08-25T16:34:00Z" : "2026-08-25T16:31:20Z",
    },
    messages,
    summary: "Appartamento ereditato a Roma Nord. Veranda da verificare prima della valutazione.",
    attention_reason: "Una verifica professionale può chiarire il prossimo passo.",
    professional_present: joined,
    automatic_replies_enabled: !joined,
    memory_items: [
      { id: "memory-1", kind: "fact", label: "Immobile", content: "Appartamento ereditato a Roma Nord", source_message_ids: [visitorMessage.id] },
      { id: "memory-2", kind: "question", label: "Domanda aperta", content: "La veranda compare nella planimetria?", source_message_ids: [assistantMessage.id] },
    ],
  };
}

const publicSpace = {
  space: {
    slug: "mauro",
    professional_name: "Mauro Rossi",
    professional_role: "agente immobiliare",
    agency: "Mauro Immobiliare",
    territory: "Roma Nord",
    hero_image_url: "/images/laggente-hero.webp",
    welcome_message: "Ciao, sono l'assistente AI di Mauro. Posso ascoltare ciò che stai valutando e aiutarti a capire quale potrebbe essere il prossimo passo utile.",
    assistant_disclosure: "LAGGENTE — assistente AI di Mauro Rossi",
    privacy_notice_version: "2026-08-22",
    capabilities: { text: true, voice_notes: true, photographs: true },
  },
};

function sendJson(response, status, value) {
  const body = JSON.stringify(value);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  response.end(body);
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { return {}; }
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
  const path = url.pathname;

  if (request.method === "GET" && path === "/api/v1/auth/session") return sendJson(response, 200, session());
  if (request.method === "POST" && path === "/api/v1/auth/logout") return sendJson(response, 200, { ok: true });
  if (request.method === "GET" && path === "/api/v1/studio/space") return sendJson(response, 200, spaceBootstrap());
  if (request.method === "GET" && path === "/api/v1/studio/messages") {
    return sendJson(response, 200, {
      messages: [
        { id: "studio-1", author_type: "studio_assistant", author_name: "Studio LAGGENTE", content: "Che lavoro fai?", created_at: "2026-08-25T16:20:00Z" },
        { id: "studio-2", author_type: "professional", author_name: "Mauro Rossi", content: "Sono un agente immobiliare a Roma Nord. Prima di una valutazione controllo provenienza, conformità urbanistica e catastale, APE, occupazione e vincoli.", created_at: "2026-08-25T16:21:00Z" },
        { id: "studio-3", author_type: "studio_assistant", author_name: "Studio LAGGENTE", content: "Ho preparato uno spazio che accoglie chi sta pensando di vendere senza trasformare la conversazione in un questionario. La bozza è pronta da rivedere.", created_at: "2026-08-25T16:22:00Z" },
      ],
      latest_email: null,
    });
  }
  if (request.method === "POST" && path === `/api/v1/studio/config/revisions/${revision.id}/activate`) {
    activated = true;
    return sendJson(response, 200, { revision: { ...revision, status: "active" } });
  }
  if (request.method === "GET" && path === "/api/v1/studio/config/revisions") {
    return sendJson(response, 200, { revisions: [{ ...revision, status: activated ? "active" : "proposed" }] });
  }
  if (request.method === "GET" && path === "/api/v1/studio/conversations") {
    return sendJson(response, 200, {
      total: 1,
      conversations: [{
        id: "demo-conversation",
        visitor_name: "Giulia",
        summary: "Appartamento ereditato a Roma Nord. Veranda da verificare.",
        last_message: assistantMessage.content,
        last_message_at: assistantMessage.created_at,
        attention_reason: "Una verifica professionale può chiarire il prossimo passo.",
        professional_present: joined,
        automatic_replies_enabled: !joined,
      }],
    });
  }
  if (request.method === "GET" && path === "/api/v1/studio/conversations/demo-conversation") return sendJson(response, 200, conversationDetail());
  if (request.method === "POST" && path === "/api/v1/studio/conversations/demo-conversation/join") {
    joined = true;
    return sendJson(response, 200, conversationDetail());
  }
  if (request.method === "POST" && path === "/api/v1/studio/conversations/demo-conversation/messages") {
    joined = true;
    return sendJson(response, 200, conversationDetail());
  }
  if (request.method === "POST" && path === "/api/v1/studio/conversations/demo-conversation/assistant-control") {
    const body = await readJson(request);
    joined = body.automatic_replies_enabled === false;
    return sendJson(response, 200, conversationDetail());
  }
  if (request.method === "GET" && path === "/api/v1/public/mauro") return sendJson(response, 200, publicSpace);
  if (request.method === "POST" && path === "/api/v1/public/mauro/conversations") {
    publicMessages = [];
    return sendJson(response, 201, { conversation: { id: "demo-conversation", space_slug: "mauro", messages: [], automatic_replies_enabled: true, professional_present: false }, messages: [] });
  }
  if (request.method === "POST" && path === "/api/v1/public/conversations/demo-conversation/messages") {
    const body = await readJson(request);
    const visitor = { ...visitorMessage, content: String(body.content || visitorMessage.content) };
    publicMessages = [visitor, assistantMessage];
    return sendJson(response, 200, { messages: publicMessages });
  }
  if (request.method === "GET" && path === "/api/v1/public/conversations/demo-conversation") {
    return sendJson(response, 200, {
      conversation: { id: "demo-conversation", space_slug: "mauro", automatic_replies_enabled: !joined, professional_present: joined },
      messages: [...publicMessages, ...(joined ? [professionalMessage] : [])],
    });
  }

  return sendJson(response, 404, { detail: `Mock endpoint not found: ${request.method} ${path}` });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`LAGGENTE video mock API listening on http://127.0.0.1:${port}`);
});
