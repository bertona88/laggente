from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .conversations import active_revision
from .models import Conversation, MemoryItem, Message, Space
from .positioning import FeaturedVertical, ProductPositioning
from .schemas import (
    RelationshipGraphEdge,
    RelationshipGraphNode,
    RelationshipGraphOut,
    RelationshipGraphProfile,
)

MAX_GRAPH_CONVERSATIONS = 60
MAX_GRAPH_NODES = 90
MAX_GRAPH_EDGES = 180


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", without_marks)).strip()


def _matches_term(corpus: str, term: str) -> bool:
    normalized_term = _normalized(term)
    if not normalized_term:
        return False
    return f" {normalized_term} " in f" {corpus} "


def _active_vertical(
    space: Space,
    positioning: ProductPositioning,
    template_id: str | None,
) -> FeaturedVertical | None:
    if template_id:
        match = next(
            (item for item in positioning.featured_verticals if item.template_id == template_id),
            None,
        )
        if match:
            return match
    normalized_role = _normalized(space.public_role)
    return next(
        (
            item
            for item in positioning.featured_verticals
            if item.id == "real_estate_it"
            and ("immobiliar" in normalized_role or "real estate" in normalized_role)
        ),
        None,
    )


def build_relationship_graph(
    db: Session,
    *,
    space: Space,
    positioning: ProductPositioning,
) -> RelationshipGraphOut:
    conversations = db.scalars(
        select(Conversation)
        .where(
            Conversation.account_id == space.account_id,
            Conversation.space_id == space.id,
            Conversation.kind == "public",
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(MAX_GRAPH_CONVERSATIONS)
    ).all()
    conversation_ids = [item.id for item in conversations]
    messages = (
        db.scalars(
            select(Message)
            .where(
                Message.account_id == space.account_id,
                Message.conversation_id.in_(conversation_ids),
                Message.author_type.in_(["visitor", "professional"]),
            )
            .order_by(Message.created_at)
        ).all()
        if conversation_ids
        else []
    )
    memories = (
        db.scalars(
            select(MemoryItem).where(
                MemoryItem.account_id == space.account_id,
                MemoryItem.space_id == space.id,
                MemoryItem.conversation_id.in_(conversation_ids),
                MemoryItem.status != "dismissed",
            )
        ).all()
        if conversation_ids
        else []
    )
    messages_by_conversation: dict[str, list[Message]] = defaultdict(list)
    memories_by_conversation: dict[str, list[MemoryItem]] = defaultdict(list)
    for message in messages:
        messages_by_conversation[message.conversation_id].append(message)
    for memory in memories:
        memories_by_conversation[memory.conversation_id].append(memory)

    revision = active_revision(db, space)
    template = revision.document.get("template", {}) if revision else {}
    template_id = str(template.get("id", "")).strip() or None
    vertical = _active_vertical(space, positioning, template_id)
    professional_id = "professional"
    nodes: list[RelationshipGraphNode] = [
        RelationshipGraphNode(
            id=professional_id,
            type="professional",
            label=space.professional_name,
            summary=f"{space.public_role} · {space.territory or 'spazio professionale'}",
            member_count=0,
            origin="primary",
        )
    ]
    edges: list[RelationshipGraphEdge] = []
    people: list[tuple[Conversation, str, str]] = []

    for index, conversation in enumerate(conversations, start=1):
        human_messages = messages_by_conversation.get(conversation.id, [])
        visitor_messages = [item for item in human_messages if item.author_type == "visitor"]
        if not visitor_messages:
            continue
        memory_text = " ".join(
            item.corrected_content or item.content
            for item in memories_by_conversation.get(conversation.id, [])
        )
        corpus = _normalized(" ".join([item.content for item in human_messages] + [memory_text]))
        first_message = visitor_messages[0].content.strip()
        label = f"Persona {index}"
        summary = first_message[:157] + "…" if len(first_message) > 160 else first_message
        person_id = f"person:{conversation.id}"
        people.append((conversation, person_id, corpus))
        nodes.append(
            RelationshipGraphNode(
                id=person_id,
                type="person",
                label=label,
                summary=summary or "Conversazione iniziata senza un riepilogo.",
                conversation_id=conversation.id,
                origin="primary",
            )
        )
        edges.append(
            RelationshipGraphEdge(
                id=f"conversation:{conversation.id}",
                source=professional_id,
                target=person_id,
                relation="conversation",
            )
        )

    for rule in sorted(vertical.graph_sets if vertical else [], key=lambda item: -item.weight):
        members = [
            person_id
            for _conversation, person_id, corpus in people
            if any(_matches_term(corpus, term) for term in rule.terms)
        ]
        if not members:
            continue
        set_id = f"set:{rule.id}"
        nodes.append(
            RelationshipGraphNode(
                id=set_id,
                type="set",
                label=rule.label,
                summary=rule.description,
                member_count=len(members),
                weight=rule.weight,
                origin="derived",
            )
        )
        edges.extend(
            RelationshipGraphEdge(
                id=f"membership:{rule.id}:{person_id.removeprefix('person:')}",
                source=person_id,
                target=set_id,
                relation="member_of",
                weight=rule.weight,
            )
            for person_id in members
        )

    nodes = nodes[:MAX_GRAPH_NODES]
    retained = {node.id for node in nodes}
    edges = [
        edge for edge in edges if edge.source in retained and edge.target in retained
    ][:MAX_GRAPH_EDGES]
    nodes[0].member_count = sum(node.type == "person" for node in nodes)
    return RelationshipGraphOut(
        center_id=professional_id,
        nodes=nodes,
        edges=edges,
        profile=RelationshipGraphProfile(
            vertical_id=vertical.id if vertical else None,
            vertical_label=vertical.label if vertical else None,
            template_id=vertical.template_id if vertical else template_id,
            source="backend_positioning" if vertical else "generic",
        ),
        bounds={
            "conversation_limit": MAX_GRAPH_CONVERSATIONS,
            "node_limit": MAX_GRAPH_NODES,
            "edge_limit": MAX_GRAPH_EDGES,
        },
    )
