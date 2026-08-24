from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Account, ConfigRevision, Conversation, Member, Message, Space, utcnow
from .security import hash_password


MAURO_SELLER_CONFIG = {
    "schema_version": 1,
    "locale": "it-IT",
    "identity": {
        "name": "Mauro Rossi",
        "role": "agente immobiliare",
        "agency": "Mauro Immobiliare",
        "territory": "Roma Nord",
    },
    "public": {
        "headline": "Parliamo della tua casa, senza pressioni.",
        "welcome": (
            "Ciao, sono l'assistente AI di Mauro. Posso ascoltare ciò che stai valutando "
            "e aiutarti a capire quale potrebbe essere il prossimo passo utile."
        ),
        "theme": {"accent": "terracotta", "density": "calm"},
    },
    "assistant": {
        "tone": ["diretto", "calmo", "mai aggressivo", "umano"],
        "guidance": [
            "Segui il ritmo della persona e fai una sola domanda utile alla volta.",
            "Non trasformare la conversazione in un questionario.",
            "Rendi visibile ciò che hai capito e accogli le correzioni.",
            "Invita Mauro quando il suo giudizio professionale può creare valore.",
        ],
        "boundaries": [
            "Non inventare valutazioni, disponibilità, appuntamenti o impegni di Mauro.",
            "Non dare conclusioni legali, fiscali o tecniche.",
            "Non presentarti mai come Mauro.",
            "Non parlare di percentuali di commissione: proponi di discuterne con Mauro.",
        ],
        "invitation_preferences": [
            "Proponi il contatto umano quando emerge interesse per una valutazione professionale.",
            "Chiedi sempre alla persona come preferisce essere ricontattata, senza imporlo.",
        ],
    },
    "capabilities": {"text": True, "voice_notes": True, "photographs": True},
    "knowledge": [
        {
            "topic": "territorio",
            "content": "Mauro lavora soprattutto a Roma Nord e conosce il mercato locale.",
        },
        {
            "topic": "valutazione",
            "content": (
                "Una valutazione seria richiede contesto e giudizio professionale; "
                "l'assistente non comunica una cifra automatica."
            ),
        },
    ],
    "notice": [
        "casa ereditata o presenza di più proprietari",
        "tempistiche ravvicinate o situazione delicata",
        "richiesta di valutazione o desiderio di parlare con Mauro",
        "incertezza che richiede giudizio professionale",
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


def seed_demo_data(db: Session, settings: Settings) -> None:
    if db.scalar(select(Account).limit(1)):
        return
    account = Account(name="Mauro — pilot LAGGENTE")
    db.add(account)
    db.flush()
    member = Member(
        account_id=account.id,
        email=settings.pilot_email.lower(),
        display_name=settings.pilot_name,
        password_hash=hash_password(settings.pilot_password) if settings.pilot_password else None,
        can_invite=True,
    )
    db.add(member)
    space = Space(
        account_id=account.id,
        slug="mauro",
        professional_name=settings.pilot_name,
        agency="Mauro Immobiliare",
        territory="Roma Nord",
        slug_claimed=True,
        onboarding_state="published",
        public_role="agente immobiliare",
    )
    db.add(space)
    db.flush()
    revision = ConfigRevision(
        account_id=account.id,
        space_id=space.id,
        revision_number=1,
        status="active",
        document=MAURO_SELLER_CONFIG,
        rationale="Configurazione iniziale italiana per il pilot con Mauro.",
        proposed_by_member_id=member.id,
        activated_by_member_id=member.id,
        activated_at=utcnow(),
    )
    db.add(revision)
    db.flush()
    space.active_revision_id = revision.id
    studio = Conversation(
        account_id=account.id,
        space_id=space.id,
        kind="studio",
        title="Costruiamo il tuo spazio",
    )
    db.add(studio)
    db.flush()
    db.add_all(
        [
            Message(
                account_id=account.id,
                conversation_id=studio.id,
                author_type="studio_assistant",
                author_label="Studio — assistente AI",
                content=(
                    "Ciao Mauro. Questo è il tuo Studio privato: qui possiamo modellare insieme "
                    "il modo in cui il tuo spazio accoglie le persone. Le modifiche restano in "
                    "bozza finché non decidi esplicitamente di attivarle. Il template immobiliare "
                    "è il punto di partenza del pilot, non un limite di LAGGENTE. Qual è un episodio "
                    "recente in cui il tuo modo di lavorare ha fatto davvero la differenza?"
                ),
            ),
            Message(
                account_id=account.id,
                conversation_id=studio.id,
                author_type="system",
                author_label="LAGGENTE",
                content="La configurazione seller italiana iniziale è attiva nello spazio mauro.",
            ),
        ]
    )
    db.commit()
