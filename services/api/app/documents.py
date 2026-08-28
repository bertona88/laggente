from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ConfigRevision, Document


ALLOWED_DOCUMENT_MEDIA_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
}
MAX_EXTRACTED_DOCUMENT_CHARACTERS = 120_000
MAX_PDF_PAGES = 100
MAX_DOCX_UNCOMPRESSED_BYTES = 30 * 1024 * 1024


class DocumentExtractionError(ValueError):
    pass


def document_content_url(document: Document) -> str:
    return f"/api/v1/documents/{document.id}/content"


def _normalized_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\t\f\v ]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    if not value:
        raise DocumentExtractionError("Il documento non contiene testo leggibile")
    return value[:MAX_EXTRACTED_DOCUMENT_CHARACTERS]


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise DocumentExtractionError("Il file DOCX non è valido")
            total_uncompressed = sum(item.file_size for item in archive.infolist())
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise DocumentExtractionError("Il file DOCX espanso è troppo grande")
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as exc:
        raise DocumentExtractionError("Il file DOCX non è valido") from exc
    parts: list[str] = []
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name == "t" and element.text:
            parts.append(element.text)
        elif local_name in {"p", "br"}:
            parts.append("\n")
    return _normalized_text(" ".join(parts))


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentExtractionError(
                f"Il PDF supera il limite di {MAX_PDF_PAGES} pagine"
            )
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError("Il PDF non è leggibile") from exc
    return _normalized_text(text)


def document_magic_matches(data: bytes, media_type: str) -> bool:
    if media_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return data.startswith(b"PK\x03\x04")
    if media_type in {"text/plain", "text/markdown", "text/csv"}:
        if b"\x00" in data[:4096]:
            return False
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return False
        return True
    return False


def extract_document_text(data: bytes, media_type: str) -> str:
    if not data or not document_magic_matches(data, media_type):
        raise DocumentExtractionError("Il contenuto non corrisponde al tipo di documento")
    if media_type == "application/pdf":
        return _pdf_text(data)
    if media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _docx_text(data)
    if media_type in {"text/plain", "text/markdown", "text/csv"}:
        return _normalized_text(data.decode("utf-8-sig"))
    raise DocumentExtractionError("Tipo di documento non supportato")


def document_storage_key(
    *, account_id: str, space_id: str, conversation_id: str | None, opaque_name: str
) -> str:
    if conversation_id:
        return f"documents/{account_id}/conversations/{conversation_id}/{opaque_name}"
    return f"documents/{account_id}/studio/{space_id}/{opaque_name}"


def document_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def knowledge_document_ids(configuration: dict | None) -> set[str]:
    if not configuration:
        return set()
    values = configuration.get("knowledge")
    if not isinstance(values, list):
        return set()
    result: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        document_id = value.get("document_id")
        if value.get("type") == "document" and isinstance(document_id, str):
            result.add(document_id)
    return result


def revision_document_states(
    db: Session, *, account_id: str, space_id: str
) -> tuple[set[str], set[str]]:
    active = db.scalar(
        select(ConfigRevision)
        .where(
            ConfigRevision.account_id == account_id,
            ConfigRevision.space_id == space_id,
            ConfigRevision.status == "active",
        )
        .order_by(ConfigRevision.revision_number.desc())
        .limit(1)
    )
    latest_draft = db.scalar(
        select(ConfigRevision)
        .where(
            ConfigRevision.account_id == account_id,
            ConfigRevision.space_id == space_id,
            ConfigRevision.status == "draft",
        )
        .order_by(ConfigRevision.revision_number.desc())
        .limit(1)
    )
    return (
        knowledge_document_ids(active.document) if active else set(),
        knowledge_document_ids(latest_draft.document) if latest_draft else set(),
    )


def validate_knowledge_document_references(
    db: Session, *, account_id: str, space_id: str, configuration: dict
) -> None:
    knowledge = configuration.get("knowledge")
    if isinstance(knowledge, list):
        for item in knowledge:
            if not isinstance(item, dict) or item.get("type") != "document":
                continue
            document_id = item.get("document_id")
            if not isinstance(document_id, str) or not document_id.strip():
                raise DocumentExtractionError(
                    "La configurazione contiene un riferimento documento non valido"
                )
    referenced = knowledge_document_ids(configuration)
    if not referenced:
        return
    available = set(
        db.scalars(
            select(Document.id).where(
                Document.id.in_(referenced),
                Document.account_id == account_id,
                Document.space_id == space_id,
                Document.scope == "studio",
                Document.status == "ready",
            )
        ).all()
    )
    if available != referenced:
        raise DocumentExtractionError(
            "La configurazione contiene documenti mancanti o non appartenenti a questo Studio"
        )


def safe_document_path(upload_dir: Path, storage_key: str) -> Path:
    base = upload_dir.resolve()
    target = (upload_dir / storage_key).resolve()
    if not target.is_relative_to(base):
        raise RuntimeError("Document path escaped the private upload directory")
    return target
