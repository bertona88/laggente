from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import io
from pathlib import Path
import zipfile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select

from app import database
from app.documents import extract_document_text
from app.models import Account, Document, Event, Space, utcnow
from app.retention import STALE_UNBOUND_ATTACHMENT_TTL, discard_stale_unbound_documents


TEXT = b"Guida privata dello Studio: ascoltare prima di proporre."


def _login(client) -> None:
    result = client.post(
        "/api/v1/auth/pilot-login",
        json={
            "email": "mauro@laggente.com",
            "password": "password-pilot-molto-sicura",
        },
    )
    assert result.status_code == 200, result.text


def _upload_studio_document(client, name: str = "guida.txt") -> dict:
    response = client.post(
        "/api/v1/studio/documents",
        files={"file": (name, TEXT, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]


def test_studio_library_is_private_until_an_explicit_revision_is_activated(
    professional_client,
):
    document = _upload_studio_document(professional_client)
    document_id = document["id"]
    assert document["scope"] == "studio"
    assert document["public_state"] == "private"
    assert professional_client.get(document["download_url"]).content == TEXT

    proposed = professional_client.post(
        f"/api/v1/studio/documents/{document_id}/public-proposal",
        json={"enabled": True},
    )
    assert proposed.status_code == 200, proposed.text
    proposal = proposed.json()
    assert proposal["document"]["public_state"] == "draft"
    revision_id = proposal["revision"]["id"]

    # Drafting never changes the active public configuration.
    active_before = professional_client.get("/api/v1/studio/space").json()["active_revision"]
    assert document_id not in str(active_before["document"])

    activated = professional_client.post(
        f"/api/v1/studio/config/revisions/{revision_id}/activate"
    )
    assert activated.status_code == 200, activated.text
    assert document_id in str(activated.json()["document"])
    listed = professional_client.get("/api/v1/studio/documents").json()
    assert listed[0]["public_state"] == "active"

    blocked = professional_client.delete(f"/api/v1/documents/{document_id}")
    assert blocked.status_code == 409
    removal = professional_client.post(
        f"/api/v1/studio/documents/{document_id}/public-proposal",
        json={"enabled": False},
    )
    assert removal.status_code == 200
    removal_revision_id = removal.json()["revision"]["id"]
    assert professional_client.post(
        f"/api/v1/studio/config/revisions/{removal_revision_id}/activate"
    ).status_code == 200
    assert professional_client.delete(f"/api/v1/documents/{document_id}").status_code == 204
    assert professional_client.get(document["download_url"]).status_code == 404


def test_configuration_rejects_a_document_outside_the_professionals_tenant(
    professional_client,
):
    space_detail = professional_client.get("/api/v1/studio/space").json()
    configuration = deepcopy(space_detail["active_revision"]["document"])
    with database.SessionLocal() as db:
        foreign_account = Account(name="Altro Studio")
        db.add(foreign_account)
        db.flush()
        foreign_space = Space(
            account_id=foreign_account.id,
            slug="altro-studio",
            professional_name="Altra Persona",
            public_role="professionista",
        )
        db.add(foreign_space)
        db.flush()
        foreign_document = Document(
            account_id=foreign_account.id,
            space_id=foreign_space.id,
            scope="studio",
            uploader_type="professional",
            storage_key=f"documents/{foreign_account.id}/foreign.txt",
            original_name="foreign.txt",
            media_type="text/plain",
            size_bytes=7,
            sha256="0" * 64,
            extracted_text="privato",
            status="ready",
        )
        db.add(foreign_document)
        db.commit()
        foreign_document_id = foreign_document.id
    configuration["knowledge"].append(
        {"type": "document", "document_id": foreign_document_id, "title": "foreign.txt"}
    )
    response = professional_client.post(
        "/api/v1/studio/config/revisions",
        json={"document": configuration, "rationale": "riferimento non autorizzato"},
    )
    assert response.status_code == 422
    assert "non appartenenti" in response.json()["detail"]


def test_visitor_document_is_bound_to_a_message_and_visible_to_both_participants(
    client, public_conversation
):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/documents",
        headers=headers,
        files={"file": ("situazione.txt", b"Casa ereditata da chiarire.", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()["document"]
    document_id = document["id"]
    assert client.get(document["download_url"], headers=headers).content == b"Casa ereditata da chiarire."
    assert client.get(
        document["download_url"], headers={"X-Conversation-Token": "sbagliato"}
    ).status_code == 404

    sent = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={"document_id": document_id, "client_message_id": "visitor-document-1"},
    )
    assert sent.status_code == 200, sent.text
    visitor_message = sent.json()["messages"][0]
    assert visitor_message["content_type"] == "document"
    assert visitor_message["document"]["id"] == document_id
    model_call = client.app.state.assistant_service.public_calls[-1]
    assert model_call["conversation_id"] == conversation_id
    assert model_call["document_inputs"][0].extracted_text == "Casa ereditata da chiarire."

    followup = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Possiamo parlarne con calma."},
    )
    assert followup.status_code == 200
    historical = client.app.state.assistant_service.public_calls[-1]["document_inputs"][0]
    assert historical.document_id == document_id
    assert historical.extracted_text is None

    _login(client)
    client.cookies.delete("laggente_visitor")
    professional_view = client.get(f"/api/v1/studio/conversations/{conversation_id}")
    assert professional_view.status_code == 200
    projected = next(
        item for item in professional_view.json()["messages"] if item["id"] == visitor_message["id"]
    )
    assert projected["document"]["name"] == "situazione.txt"
    room = client.get(f"/api/v1/studio/conversations/{conversation_id}/documents")
    assert [item["id"] for item in room.json()] == [document_id]


def test_professional_can_share_a_document_and_retry_the_message_safely(
    client, public_conversation
):
    conversation_id, token = public_conversation
    _login(client)
    uploaded = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/documents",
        files={"file": ("riepilogo.md", b"# Riepilogo\nProssimo passo condiviso.", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()["document"]
    payload = {
        "document_id": document["id"],
        "client_message_id": "professional-document-1",
    }
    sent = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages", json=payload
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["automatic_replies_enabled"] is False
    professional_messages = [
        item for item in sent.json()["messages"] if item["author_type"] == "professional"
    ]
    assert len(professional_messages) == 1
    assert professional_messages[0]["document"]["id"] == document["id"]

    replay = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages", json=payload
    )
    assert replay.status_code == 200, replay.text
    assert sum(
        item["author_type"] == "professional" for item in replay.json()["messages"]
    ) == 1
    public_download = client.get(
        document["download_url"], headers={"X-Conversation-Token": token}
    )
    assert public_download.status_code == 200


def test_invalid_document_content_and_stale_unbound_cleanup(client, public_conversation):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    invalid = client.post(
        f"/api/v1/public/conversations/{conversation_id}/documents",
        headers=headers,
        files={"file": ("falso.pdf", b"non un pdf", "application/pdf")},
    )
    assert invalid.status_code == 422

    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/documents",
        headers=headers,
        files={"file": ("bozza.csv", b"campo,valore\nuso,temporaneo", "text/csv")},
    ).json()["document"]
    with database.SessionLocal() as db:
        document = db.get(Document, uploaded["id"])
        document.created_at = utcnow() - STALE_UNBOUND_ATTACHMENT_TTL - timedelta(seconds=1)
        target = Path(client.app.state.settings.upload_dir) / document.storage_key
        assert target.is_file()
        db.commit()
        deleted = discard_stale_unbound_documents(
            db,
            client.app.state.settings,
            now=utcnow(),
            conversation_id=conversation_id,
        )
        assert deleted == 1
        assert db.get(Document, uploaded["id"]) is None
        event = db.scalar(
            select(Event).where(
                Event.event_type == "document_draft_expired",
                Event.conversation_id == conversation_id,
            )
        )
        assert event is not None
        assert not target.exists()


def test_text_extractors_accept_markdown_and_csv():
    assert extract_document_text(b"# Titolo\nContenuto", "text/markdown") == "# Titolo\nContenuto"
    assert extract_document_text(b"nome,valore\na,1", "text/csv") == "nome,valore\na,1"


def test_pdf_and_docx_extractors_accept_readable_office_documents():
    pdf_buffer = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 30 100 Td (Guida dello Studio) Tj ET")
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(pdf_buffer)
    assert "Guida dello Studio" in extract_document_text(
        pdf_buffer.getvalue(), "application/pdf"
    )

    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fonte professionale</w:t></w:r></w:p></w:body></w:document>""",
        )
    assert "Fonte professionale" in extract_document_text(
        docx_buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
