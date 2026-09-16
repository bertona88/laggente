from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.positioning import load_product_positioning


def test_public_positioning_is_generic_with_real_estate_weighted_first(client):
    response = client.get("/api/v1/product/positioning")

    assert response.status_code == 200
    body = response.json()
    assert body["opening_question"] == "Che lavoro fai?"
    assert "Professionisti" in body["audience"]
    assert body["featured_verticals"][0]["id"] == "real_estate_it"
    assert body["featured_verticals"][0]["template_id"] == "seller_it_v1"
    assert "conformità urbanistica e catastale" in body["featured_verticals"][0]["example_answer"]
    assert "graph_sets" not in body["featured_verticals"][0]


def test_backend_weights_control_vertical_order():
    raw = json.dumps(
        {
            "audience": "Professionisti indipendenti",
            "opening_question": "Che lavoro fai?",
            "featured_verticals": [
                {
                    "id": "architecture_it",
                    "label": "Architetti",
                    "weight": 40,
                    "status": "example",
                    "example_answer": "Sono un architetto.",
                    "headline": "Uno spazio per uno studio di architettura.",
                    "description": "Un esempio da validare.",
                },
                {
                    "id": "real_estate_it",
                    "label": "Agenti immobiliari",
                    "weight": 100,
                    "status": "pilot",
                    "template_id": "seller_it_v1",
                    "example_answer": "Sono un agente immobiliare.",
                    "headline": "Partiamo dagli agenti immobiliari.",
                    "description": "Il primo settore del pilot.",
                },
            ],
        }
    )

    result = load_product_positioning(raw)

    assert [item.id for item in result.featured_verticals] == [
        "real_estate_it",
        "architecture_it",
    ]
    assert result.featured_verticals[0].graph_sets[0].id == "selling_intent"
    assert result.featured_verticals[1].graph_sets == []


def test_backend_can_explicitly_replace_graph_set_weights():
    raw = json.dumps(
        {
            "audience": "Professionisti indipendenti",
            "opening_question": "Che lavoro fai?",
            "featured_verticals": [
                {
                    "id": "real_estate_it",
                    "label": "Agenti immobiliari",
                    "weight": 100,
                    "status": "pilot",
                    "template_id": "seller_it_v1",
                    "example_answer": "Sono un agente immobiliare.",
                    "headline": "Partiamo dagli agenti immobiliari.",
                    "description": "Il primo settore del pilot.",
                    "graph_sets": [
                        {
                            "id": "valuation",
                            "label": "Valutazione prioritaria",
                            "weight": 250,
                            "terms": ["valutazione"],
                            "description": "Un insieme regolato dal backend.",
                        }
                    ],
                }
            ],
        }
    )

    result = load_product_positioning(raw)

    assert [(item.id, item.weight) for item in result.featured_verticals[0].graph_sets] == [
        ("valuation", 250)
    ]


def test_backend_positioning_rejects_duplicate_verticals():
    vertical = {
        "id": "real_estate_it",
        "label": "Agenti immobiliari",
        "weight": 100,
        "status": "pilot",
        "example_answer": "Sono un agente immobiliare.",
        "headline": "Partiamo dagli agenti immobiliari.",
        "description": "Il primo settore del pilot.",
    }
    raw = json.dumps(
        {
            "audience": "Professionisti",
            "opening_question": "Che lavoro fai?",
            "featured_verticals": [vertical, vertical],
        }
    )

    with pytest.raises(ValidationError, match="must be unique"):
        load_product_positioning(raw)


def test_homepage_contract_supports_existing_overrides_without_changing_market():
    from app.positioning import public_product_positioning

    raw = json.dumps({
        "audience": "Architetti",
        "opening_question": "Di quali progetti ti occupi?",
        "featured_verticals": [{
            "id": "architecture_it", "label": "Architetti", "weight": 100,
            "example_answer": "Progetto case.", "headline": "Architettura",
            "description": "Consulenza per ristrutturazioni.",
        }],
    })
    public = public_product_positioning(load_product_positioning(raw))
    assert "assistente AI" in public.homepage.headline
    assert public.featured_verticals[0].conversation_example is None
    assert public.featured_verticals[0].id == "architecture_it"


def test_homepage_copy_and_example_are_backend_owned():
    from app.positioning import DEFAULT_PRODUCT_POSITIONING, public_product_positioning

    payload = json.loads(json.dumps(DEFAULT_PRODUCT_POSITIONING))
    payload["homepage"] = {"headline": "Il tuo assistente, preparato da te."}
    payload["featured_verticals"][0]["conversation_example"] = {
        "instruction": "Chiedi la zona.", "visitor": "Vorrei vendere.",
        "assistant": "Dove si trova?", "professional": "Ti seguo io.",
    }
    public = public_product_positioning(load_product_positioning(json.dumps(payload)))
    assert public.homepage.headline == payload["homepage"]["headline"]
    assert public.featured_verticals[0].conversation_example.visitor == "Vorrei vendere."
    assert "graph_sets" not in public.model_dump()["featured_verticals"][0]
