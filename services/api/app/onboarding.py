from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import Account, Conversation, Member, Message, Space


@dataclass(frozen=True)
class ProvisionedProfessional:
    account: Account
    member: Member
    space: Space
    studio: Conversation


def pending_space_slug() -> str:
    """Return an unreachable-until-published placeholder that still satisfies DB constraints."""

    return f"pending-{uuid.uuid4().hex[:20]}"


def provision_private_professional_space(
    db: Session,
    *,
    email: str,
    onboarding_state: str,
) -> ProvisionedProfessional:
    """Create the minimal isolated Studio state for a verified or invited professional."""

    if onboarding_state not in {"invited", "building"}:
        raise ValueError("A new professional space must begin invited or building")
    account = Account(name="Spazio professionale in preparazione")
    db.add(account)
    db.flush()
    member = Member(
        account_id=account.id,
        email=email,
        display_name="Professionista",
        role="professional",
        password_hash=None,
        is_active=True,
        can_invite=False,
    )
    db.add(member)
    space = Space(
        account_id=account.id,
        slug=pending_space_slug(),
        professional_name="Professionista",
        agency=None,
        territory=None,
        public_role="professionista",
        locale="it-IT",
        is_active=False,
        slug_claimed=False,
        onboarding_state=onboarding_state,
    )
    db.add(space)
    db.flush()
    studio = Conversation(
        account_id=account.id,
        space_id=space.id,
        kind="studio",
        title="Costruiamo il tuo spazio",
    )
    db.add(studio)
    db.flush()
    db.add(
        Message(
            account_id=account.id,
            conversation_id=studio.id,
            author_type="studio_assistant",
            author_label="Studio — assistente AI",
            content=(
                "Ti diamo il benvenuto nel tuo Studio privato. Raccontami che lavoro fai e come "
                "vuoi accogliere le persone: preparerò una prima bozza, ma nulla diventerà "
                "pubblico finché non la attiverai tu."
            ),
        )
    )
    return ProvisionedProfessional(account=account, member=member, space=space, studio=studio)


def starter_space_configuration() -> dict:
    """Generic Italian starting point for a professional's first Studio revision.

    The document is intentionally useful but identity-neutral. Studio replaces the neutral
    material with what the professional actually says; this is never activated automatically.
    """

    return {
        "schema_version": 1,
        "locale": "it-IT",
        "identity": {
            "name": "Il professionista",
            "role": "professionista",
            "agency": None,
            "territory": None,
        },
        "public": {
            "headline": "Uno spazio per parlare con calma.",
            "welcome": (
                "Ciao, sono LAGGENTE, l'assistente AI di questo professionista. "
                "Posso ascoltare ciò che hai in mente e coinvolgere la persona giusta quando "
                "il suo giudizio può essere utile. Da dove vuoi partire?"
            ),
            "theme": {"accent": "terracotta", "density": "calm"},
        },
        "assistant": {
            "tone": ["calmo", "chiaro", "mai aggressivo"],
            "guidance": [
                "Segui l'intenzione della persona e fai una sola domanda utile alla volta.",
                "Non trasformare la conversazione in un questionario.",
                "Rendi visibile ciò che hai capito e accogli le correzioni.",
                "Invita il professionista quando il suo giudizio può creare valore.",
            ],
            "boundaries": [
                "Non inventare valutazioni, disponibilità, appuntamenti o impegni.",
                "Non dare conclusioni legali, fiscali o tecniche.",
                "Non presentarti mai come il professionista.",
            ],
            "invitation_preferences": [
                "Rendi sempre semplice chiedere il contatto con il professionista.",
            ],
        },
        "capabilities": {"text": True, "voice_notes": True, "photographs": True},
        "knowledge": [],
        "notice": [
            "richiesta di una valutazione professionale",
            "situazione delicata o urgenza",
            "desiderio di parlare con il professionista",
            "incertezza che richiede giudizio umano",
        ],
        "template": {
            "id": "seller_it_v1",
            "label": "Prima conversazione con chi sta pensando di vendere",
            "topics_are_optional": True,
            "possible_topics": [
                "immobile e zona",
                "rapporto della persona con l'immobile",
                "motivazione e tempi",
                "proprietà, stato e occupazione",
                "aspettative e interesse per una valutazione",
                "preferenza di contatto",
            ],
        },
        "extensions": {},
    }
