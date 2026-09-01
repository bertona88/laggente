from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace

import pytest

from app.assistants import (
    AgentsAssistantService,
    AssistantUnavailable,
    PublicImageInput,
    StudioRunContext,
    _public_instructions,
    _studio_instructions,
    _studio_output_with_clickable_citations,
)
from app.models import Message


def test_exactly_two_bounded_agent_definitions(settings):
    service = AgentsAssistantService(settings)
    assert service.studio_assistant.name == "Studio assistant"
    assert service.public_assistant.name == "Public assistant"
    assert service.studio_assistant.handoffs == []
    assert service.public_assistant.handoffs == []
    assert {tool.name for tool in service.studio_assistant.tools} == {
        "inspect_active_space_configuration",
        "list_public_conversations",
        "inspect_public_conversation",
        "list_studio_documents",
        "inspect_studio_document",
        "inspect_conversation_document",
        "propose_configuration_revision",
        "web_search",
    }
    assert {tool.name for tool in service.public_assistant.tools} == {
        "search_approved_knowledge",
        "inspect_shared_document",
    }
    assert service.studio_assistant.model_settings.store is False
    assert service.public_assistant.model_settings.store is False
    assert service.product_positioning.opening_question == "Che lavoro fai?"
    assert service.product_positioning.featured_verticals[0].id == "real_estate_it"


def test_studio_instruction_uses_adaptive_correctable_elicitation():
    context = StudioRunContext(
        account_id="account",
        space_id="space",
        member_id="member",
        product_positioning={
            "opening_question": "Qual è il tuo lavoro?",
            "featured_verticals": [],
        },
    )

    instructions = _studio_instructions(SimpleNamespace(context=context), None)

    assert "Qual è il tuo lavoro?" in instructions
    assert "non è raccogliere più dati possibile" in instructions
    assert "domanda a maggior valore" in instructions
    assert "fanne una sola alla volta" in instructions
    assert "preferisci un episodio concreto" in instructions
    assert "Mantieni distinta l'evidenza esplicita dalle tue inferenze" in instructions
    assert "Non creare punteggi nascosti" in instructions
    assert "Smetti di fare domande" in instructions
    assert "bozza fino all'attivazione umana" in instructions
    assert "Usala soltanto quando il professionista chiede" in instructions
    assert "contenuti privati dello Studio" in instructions
    assert "materiale esterno non attendibile" in instructions
    assert "non dispone della ricerca web" in instructions


def test_public_instruction_does_not_offer_web_search():
    context = SimpleNamespace(
        context=SimpleNamespace(
            professional_name="Giulia",
            configuration={"identity": {"role": "Architetta"}},
        )
    )

    instructions = _public_instructions(context, None)

    assert "Non hai strumenti di ricerca web" in instructions


def test_google_calendar_adds_only_bounded_public_tools(settings):
    enabled = settings.model_copy(
        update={
            "google_calendar_enabled": True,
            "google_calendar_client_id": "client-id",
            "google_calendar_client_secret": "client-secret",
        }
    )
    service = AgentsAssistantService(enabled)
    assert {tool.name for tool in service.public_assistant.tools} == {
        "search_approved_knowledge",
        "inspect_shared_document",
        "get_calendar_availability",
        "book_calendar_appointment",
    }
    assert {tool.name for tool in service.studio_assistant.tools}.isdisjoint(
        {"get_calendar_availability", "book_calendar_appointment"}
    )
    context = SimpleNamespace(
        context=SimpleNamespace(
            professional_name="Giulia",
            configuration={"identity": {"role": "Agente immobiliare"}},
            runtime_settings=enabled,
        )
    )
    instructions = _public_instructions(context, None)
    assert "soltanto dopo che la persona ha scelto un orario esatto" in instructions
    assert "Non dichiarare confermato" in instructions


def test_studio_web_citations_become_clickable_persisted_markdown():
    text = "Ho trovato un profilo pubblico coerente."
    result = SimpleNamespace(
        final_output=text,
        new_items=[
            SimpleNamespace(
                raw_item={
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "start_index": 13,
                                    "end_index": len(text),
                                    "title": "Profilo professionale",
                                    "url": "https://www.example.com/profilo",
                                },
                                {
                                    "type": "url_citation",
                                    "start_index": 13,
                                    "end_index": len(text),
                                    "title": "Schema non sicuro",
                                    "url": "javascript:alert(1)",
                                },
                            ],
                        }
                    ],
                }
            )
        ],
    )

    assert _studio_output_with_clickable_citations(result) == (
        f"{text} ([example.com](<https://www.example.com/profilo>))"
    )


def test_agent_mail_adds_tools_to_studio_without_creating_another_agent(settings):
    enabled = settings.model_copy(
        update={
            "agent_mail_enabled": True,
            "agent_mail_inbound_secret": "x" * 32,
        }
    )
    service = AgentsAssistantService(enabled)
    assert {tool.name for tool in service.studio_assistant.tools} == {
        "inspect_active_space_configuration",
        "list_public_conversations",
        "inspect_public_conversation",
        "list_studio_documents",
        "inspect_studio_document",
        "inspect_conversation_document",
        "propose_configuration_revision",
        "web_search",
        "propose_professional_email",
        "list_professional_emails",
        "inspect_professional_email",
    }
    assert {tool.name for tool in service.public_assistant.tools} == {
        "search_approved_knowledge",
        "inspect_shared_document",
    }
    assert service.studio_assistant.handoffs == []


def test_outreach_adds_bounded_studio_tools_and_never_public_tools(settings):
    enabled = settings.model_copy(
        update={
            "agent_mail_enabled": True,
            "agent_mail_inbound_secret": "x" * 32,
            "outreach_enabled": True,
            "outreach_max_recipients": 5,
        }
    )
    service = AgentsAssistantService(enabled)
    tool_names = {tool.name for tool in service.studio_assistant.tools}

    assert {
        "web_search",
        "propose_outreach_campaign",
        "record_outreach_contact_permission",
        "propose_outreach_email",
        "list_outreach_campaigns",
        "inspect_outreach_campaign",
    }.issubset(tool_names)
    public_tool_names = {tool.name for tool in service.public_assistant.tools}
    assert public_tool_names == {
        "search_approved_knowledge",
        "inspect_shared_document",
    }
    assert public_tool_names.isdisjoint(
        {
            "web_search",
            "propose_outreach_campaign",
            "record_outreach_contact_permission",
            "propose_outreach_email",
            "list_outreach_campaigns",
            "inspect_outreach_campaign",
        }
    )
    context = StudioRunContext(
        account_id="account",
        space_id="space",
        member_id="member",
        product_positioning={"opening_question": "Che lavoro fai?", "featured_verticals": []},
        mail_enabled=True,
        outreach_enabled=True,
        runtime_settings=enabled,
    )
    instructions = _studio_instructions(SimpleNamespace(context=context), None)
    assert "Un indirizzo pubblicato online" in instructions
    assert "NON costituiscono consenso" in instructions
    assert "existing_customer_similar_services" in instructions
    assert "tu non puoi inviare" in instructions


def test_public_input_embeds_integrity_checked_private_image(settings):
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"private-image"
    storage_key = "account/conversation/image.png"
    target = settings.upload_dir / storage_key
    target.parent.mkdir(parents=True)
    target.write_bytes(image_bytes)
    message = Message(
        id="message-image",
        account_id="account",
        conversation_id="conversation",
        author_type="visitor",
        author_label="Tu",
        content="Ti invio questa fotografia.",
    )
    image = PublicImageInput(
        message_id=message.id,
        media_type="image/png",
        storage_key=storage_key,
        size_bytes=len(image_bytes),
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )

    model_input = AgentsAssistantService(settings)._public_input([message], [image])

    assert model_input[0]["role"] == "user"
    assert model_input[0]["content"][0] == {
        "type": "input_text",
        "text": "[Messaggio message-image — visitatore] Ti invio questa fotografia.",
    }
    image_part = model_input[0]["content"][1]
    assert image_part["type"] == "input_image"
    assert image_part["detail"] == "high"
    assert image_part["image_url"] == (
        "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    )


def test_public_input_rejects_private_image_integrity_mismatch(settings):
    storage_key = "account/conversation/image.png"
    target = settings.upload_dir / storage_key
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG\r\n\x1a\nchanged")
    message = Message(
        id="message-image",
        account_id="account",
        conversation_id="conversation",
        author_type="visitor",
        author_label="Tu",
        content="Fotografia.",
    )
    image = PublicImageInput(
        message_id=message.id,
        media_type="image/png",
        storage_key=storage_key,
        size_bytes=12,
        sha256="0" * 64,
    )

    with pytest.raises(AssistantUnavailable, match="integrity"):
        AgentsAssistantService(settings)._public_input([message], [image])
