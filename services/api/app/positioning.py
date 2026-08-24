from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GraphSetRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$", max_length=80)
    label: str = Field(min_length=1, max_length=120)
    weight: int = Field(ge=0, le=1000)
    terms: list[str] = Field(min_length=1, max_length=30)
    description: str = Field(min_length=1, max_length=500)

    @field_validator("terms")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        if not normalized or len(normalized) != len({value.casefold() for value in normalized}):
            raise ValueError("graph set terms must be non-empty and unique")
        return normalized


class FeaturedVertical(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$", max_length=80)
    label: str = Field(min_length=1, max_length=120)
    weight: int = Field(ge=0, le=1000)
    status: Literal["pilot", "example", "available"] = "example"
    template_id: str | None = Field(default=None, max_length=100)
    example_answer: str = Field(min_length=1, max_length=240)
    headline: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=800)
    graph_sets: list[GraphSetRule] = Field(default_factory=list, max_length=20)


class ProductPositioning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: str = Field(min_length=1, max_length=500)
    opening_question: str = Field(min_length=1, max_length=240)
    featured_verticals: list[FeaturedVertical] = Field(min_length=1, max_length=12)

    @field_validator("audience", "opening_question")
    @classmethod
    def strip_copy(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def unique_vertical_ids(self):
        ids = [item.id for item in self.featured_verticals]
        if len(ids) != len(set(ids)):
            raise ValueError("featured vertical ids must be unique")
        return self


class PublicFeaturedVertical(BaseModel):
    id: str
    label: str
    weight: int
    status: Literal["pilot", "example", "available"]
    template_id: str | None
    example_answer: str
    headline: str
    description: str


class PublicProductPositioning(BaseModel):
    audience: str
    opening_question: str
    featured_verticals: list[PublicFeaturedVertical]


def public_product_positioning(positioning: ProductPositioning) -> PublicProductPositioning:
    return PublicProductPositioning.model_validate(positioning.model_dump(mode="json"))


DEFAULT_PRODUCT_POSITIONING = {
    "audience": (
        "Professionisti che lavorano attraverso relazioni, competenza e fiducia, "
        "a partire dagli agenti immobiliari."
    ),
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
            "description": (
                "È il primo settore che stiamo rendendo concreto: un template italiano per "
                "accogliere chi sta valutando di vendere, senza trasformare la conversazione "
                "in un questionario o in una pipeline."
            ),
            "graph_sets": [
                {
                    "id": "selling_intent",
                    "label": "Sta valutando di vendere",
                    "weight": 100,
                    "terms": [
                        "vendere",
                        "venderla",
                        "venderlo",
                        "vendita",
                        "mettere in vendita",
                    ],
                    "description": "Conversazioni in cui emerge una possibile vendita.",
                },
                {
                    "id": "inherited_property",
                    "label": "Casa ereditata",
                    "weight": 95,
                    "terms": ["ereditata", "ereditato", "eredità", "successione"],
                    "description": (
                        "Persone che parlano di un immobile o di una situazione ereditaria."
                    ),
                },
                {
                    "id": "valuation",
                    "label": "Valutazione",
                    "weight": 90,
                    "terms": ["valutazione", "valutare", "stima", "quanto vale"],
                    "description": (
                        "Conversazioni in cui può essere utile il giudizio su una valutazione."
                    ),
                },
                {
                    "id": "shared_ownership",
                    "label": "Più proprietari",
                    "weight": 85,
                    "terms": ["proprietari", "comproprietari", "fratelli", "sorelle"],
                    "description": (
                        "Situazioni in cui risultano coinvolte più persone nella proprietà."
                    ),
                },
                {
                    "id": "timing",
                    "label": "Tempistiche",
                    "weight": 75,
                    "terms": ["tempistiche", "tempi", "presto", "entro", "mesi"],
                    "description": (
                        "Conversazioni in cui il momento o una scadenza possono contare."
                    ),
                },
                {
                    "id": "territory",
                    "label": "Zona e territorio",
                    "weight": 65,
                    "terms": ["zona", "quartiere", "roma nord"],
                    "description": "Persone collegate da una zona o da un contesto territoriale.",
                },
            ],
        }
    ],
}


def load_product_positioning(raw: str | None) -> ProductPositioning:
    payload = DEFAULT_PRODUCT_POSITIONING if raw is None or not raw.strip() else json.loads(raw)
    if payload is not DEFAULT_PRODUCT_POSITIONING:
        default_verticals = {
            item["id"]: item for item in DEFAULT_PRODUCT_POSITIONING["featured_verticals"]
        }
        for vertical in payload.get("featured_verticals", []):
            default = default_verticals.get(vertical.get("id"))
            if default and "graph_sets" not in vertical:
                vertical["graph_sets"] = default.get("graph_sets", [])
    positioning = ProductPositioning.model_validate(payload)
    return positioning.model_copy(
        update={
            "featured_verticals": sorted(
                positioning.featured_verticals,
                key=lambda item: (-item.weight, item.id),
            )
        }
    )
