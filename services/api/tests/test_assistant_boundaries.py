from __future__ import annotations

from app.assistants import AgentsAssistantService


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
