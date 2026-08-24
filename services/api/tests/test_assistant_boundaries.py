from __future__ import annotations

import base64
import hashlib

import pytest

from app.assistants import AssistantUnavailable, AgentsAssistantService, PublicImageInput
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
        "propose_configuration_revision",
    }
    assert service.public_assistant.tools == []
    assert service.studio_assistant.model_settings.store is False
    assert service.public_assistant.model_settings.store is False


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
        "propose_configuration_revision",
        "propose_professional_email",
        "list_professional_emails",
        "inspect_professional_email",
    }
    assert service.public_assistant.tools == []
    assert service.studio_assistant.handoffs == []


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
