"""No-code contact-center knowledge-base management (FR-CC-08 / FR-CC-13)."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.model_registry import ModelRegistry
from hub.models import ContactCenterKnowledgeBase, KnowledgeBaseDocument
from ingest.pipeline import (
    checksum_for_text,
    chunk_text,
    deterministic_embedding,
    normalize_text,
)
from ingest.models import CCProductionChunk

ARTICLE_ID_BASE = 2_000_000_000
ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".rtf",
        ".xlsx",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
    }
)
TEXT_EXTENSIONS = frozenset({".txt", ".rtf"})
WHITESPACE = re.compile(r"\s+")
WORD_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
}


class KnowledgeBaseError(ValueError):
    """Raised for invalid KB admin operations."""


def _unique_slug(name: str) -> str:
    base = slugify(name, allow_unicode=False) or "kb"
    candidate = base
    index = 2
    while ContactCenterKnowledgeBase.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def serialize_document(document: KnowledgeBaseDocument) -> dict[str, Any]:
    return {
        "id": document.pk,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "status": document.status,
        "status_message": document.status_message,
        "chunk_count": document.chunk_count,
        "uploaded_at": document.uploaded_at.isoformat(),
        "indexed_at": (
            document.indexed_at.isoformat() if document.indexed_at else None
        ),
        "uploaded_by": document.uploaded_by,
    }


def serialize_knowledge_base(
    kb: ContactCenterKnowledgeBase,
    *,
    include_documents: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": kb.pk,
        "name": kb.name,
        "slug": kb.slug,
        "scope": kb.scope,
        "description": kb.description,
        "status": kb.status,
        "status_message": kb.status_message,
        "document_count": kb.document_count,
        "chunk_count": kb.chunk_count,
        "last_reindexed_at": (
            kb.last_reindexed_at.isoformat() if kb.last_reindexed_at else None
        ),
        "created_at": kb.created_at.isoformat(),
        "updated_at": kb.updated_at.isoformat(),
        "created_by": kb.created_by,
    }
    if include_documents:
        payload["documents"] = [
            serialize_document(document)
            for document in kb.documents.all()
        ]
    return payload


def list_knowledge_bases() -> list[dict[str, Any]]:
    return [
        serialize_knowledge_base(kb)
        for kb in ContactCenterKnowledgeBase.objects.all()
    ]


def get_knowledge_base(kb_id: int) -> dict[str, Any]:
    kb = ContactCenterKnowledgeBase.objects.prefetch_related("documents").get(
        pk=kb_id
    )
    return serialize_knowledge_base(kb, include_documents=True)


@transaction.atomic
def create_knowledge_base(
    *,
    name: str,
    scope: str = "contact_center",
    description: str = "",
    username: str = "",
) -> dict[str, Any]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise KnowledgeBaseError("name must be a non-empty string")
    if ContactCenterKnowledgeBase.objects.filter(name__iexact=cleaned_name).exists():
        raise KnowledgeBaseError("knowledge base with this name already exists")
    kb = ContactCenterKnowledgeBase.objects.create(
        name=cleaned_name,
        slug=_unique_slug(cleaned_name),
        scope=(scope or "contact_center").strip() or "contact_center",
        description=description.strip(),
        status=ContactCenterKnowledgeBase.STATUS_IDLE,
        created_by=username,
    )
    return serialize_knowledge_base(kb, include_documents=True)


@transaction.atomic
def delete_knowledge_base(kb_id: int) -> None:
    kb = ContactCenterKnowledgeBase.objects.get(pk=kb_id)
    article_ids = list(kb.documents.values_list("article_id", flat=True))
    if article_ids:
        CCProductionChunk.objects.filter(article_id__in=article_ids).delete()
    kb.delete()


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise KnowledgeBaseError("invalid docx file") from exc
    root = ET.fromstring(xml_bytes)
    parts = [
        node.text or ""
        for node in root.findall(".//w:t", WORD_NS)
        if node.text
    ]
    text = normalize_text(" ".join(parts))
    if not text:
        raise KnowledgeBaseError("docx file contains no extractable text")
    return text


def _extract_doc_text(filename: str, data: bytes) -> str:
    """Best-effort text from legacy .doc (OLE) for local seed / Hub upload."""
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    chunks: list[str] = []
    for encoding in ("utf-16-le", "cp1251", "latin-1"):
        try:
            decoded = data.decode(encoding, errors="ignore")
        except Exception:
            continue
        # Keep runs of letters/digits/punctuation (incl. Cyrillic).
        runs = re.findall(
            r"[\w\u0400-\u04FF][\w\u0400-\u04FF\s.,:;!?%№«»\"'()\-/]{8,}",
            decoded,
            flags=re.UNICODE,
        )
        chunks.extend(runs)
    text = normalize_text(" ".join(chunks))
    if len(text) >= 40:
        return text
    return normalize_text(f"{stem} {filename}")


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        PdfReader = None  # type: ignore[misc, assignment]
    if PdfReader is not None:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = normalize_text("\n".join(pages))
        if text:
            return text
    decoded = data.decode("latin-1", errors="ignore")
    text = normalize_text(
        "".join(character if character.isprintable() else " " for character in decoded)
    )
    if not text:
        raise KnowledgeBaseError("pdf file contains no extractable text")
    return text


def extract_document_text(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise KnowledgeBaseError(f"unsupported file type; allowed: {allowed}")
    if not data:
        raise KnowledgeBaseError("uploaded file is empty")
    if extension in TEXT_EXTENSIONS:
        text = normalize_text(data.decode("utf-8", errors="ignore"))
        if not text:
            raise KnowledgeBaseError("text file is empty")
        return text
    if extension == ".docx":
        return _extract_docx_text(data)
    if extension == ".doc":
        return _extract_doc_text(filename, data)
    if extension == ".pdf":
        return _extract_pdf_text(data)
    # Binary office/image formats: keep a searchable filename marker for MVP.
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    return normalize_text(f"{stem} {filename}")


@transaction.atomic
def upload_document(
    kb_id: int,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    username: str = "",
    reindex: bool = True,
) -> dict[str, Any]:
    kb = ContactCenterKnowledgeBase.objects.select_for_update().get(pk=kb_id)
    cleaned_name = Path(filename).name.strip()
    if not cleaned_name:
        raise KnowledgeBaseError("filename is required")
    text = extract_document_text(cleaned_name, data)
    # Temporary unique article_id until PK is known.
    provisional_article_id = ARTICLE_ID_BASE + (
        KnowledgeBaseDocument.objects.count() + 1
    ) * 10_000 + (kb.pk % 10_000)
    while KnowledgeBaseDocument.objects.filter(
        article_id=provisional_article_id
    ).exists():
        provisional_article_id += 1
    document = KnowledgeBaseDocument.objects.create(
        knowledge_base=kb,
        filename=cleaned_name,
        content_type=content_type or "",
        size_bytes=len(data),
        status=KnowledgeBaseDocument.STATUS_UPLOADED,
        extracted_text=text,
        uploaded_by=username,
        article_id=provisional_article_id,
    )
    document.article_id = ARTICLE_ID_BASE + document.pk
    document.save(update_fields=("article_id",))
    kb.document_count = kb.documents.count()
    kb.status = ContactCenterKnowledgeBase.STATUS_IDLE
    kb.status_message = "Документ загружен, требуется переиндексация"
    kb.save(
        update_fields=(
            "document_count",
            "status",
            "status_message",
            "updated_at",
        )
    )
    if reindex:
        reindex_knowledge_base(kb.pk)
        kb.refresh_from_db()
        document.refresh_from_db()
    return {
        "knowledge_base": serialize_knowledge_base(kb, include_documents=True),
        "document": serialize_document(document),
    }


@transaction.atomic
def delete_document(kb_id: int, document_id: int) -> dict[str, Any]:
    kb = ContactCenterKnowledgeBase.objects.select_for_update().get(pk=kb_id)
    document = kb.documents.get(pk=document_id)
    CCProductionChunk.objects.filter(article_id=document.article_id).delete()
    document.delete()
    kb.document_count = kb.documents.count()
    kb.chunk_count = sum(kb.documents.values_list("chunk_count", flat=True))
    kb.status_message = "Документ удалён"
    kb.save(
        update_fields=(
            "document_count",
            "chunk_count",
            "status_message",
            "updated_at",
        )
    )
    return serialize_knowledge_base(kb, include_documents=True)


@transaction.atomic
def reindex_knowledge_base(kb_id: int) -> dict[str, Any]:
    kb = ContactCenterKnowledgeBase.objects.select_for_update().get(pk=kb_id)
    kb.status = ContactCenterKnowledgeBase.STATUS_INDEXING
    kb.status_message = "Индексация выполняется"
    kb.save(update_fields=("status", "status_message", "updated_at"))

    registry = ModelRegistry.load()
    profile = registry.get_profile("kb_cc_production")
    total_chunks = 0
    try:
        for document in kb.documents.select_for_update():
            text = normalize_text(document.extracted_text)
            if not text:
                document.status = KnowledgeBaseDocument.STATUS_ERROR
                document.status_message = "Нет текста для индексации"
                document.chunk_count = 0
                document.save(
                    update_fields=(
                        "status",
                        "status_message",
                        "chunk_count",
                    )
                )
                continue
            chunks = chunk_text(
                text,
                chunk_size=profile.chunk_size_tokens,
                overlap=profile.chunk_overlap_tokens,
            )
            checksum = checksum_for_text(text)
            CCProductionChunk.objects.filter(
                article_id=document.article_id
            ).delete()
            CCProductionChunk.objects.bulk_create(
                [
                    CCProductionChunk(
                        article_id=document.article_id,
                        version_id=document.pk,
                        chunk_index=index,
                        title=document.filename,
                        content=chunk,
                        permalink=(
                            f"https://suz.local/admin-kb/{kb.slug}"
                            f"/documents/{document.pk}"
                        ),
                        locale="ru",
                        visibility_scope=["kc_operator", "contact_center"],
                        checksum=checksum,
                        embedding_model=profile.embedding_model,
                        embedding=deterministic_embedding(chunk),
                        is_active=True,
                    )
                    for index, chunk in enumerate(chunks)
                ]
            )
            document.status = KnowledgeBaseDocument.STATUS_INDEXED
            document.status_message = ""
            document.chunk_count = len(chunks)
            document.indexed_at = timezone.now()
            document.save(
                update_fields=(
                    "status",
                    "status_message",
                    "chunk_count",
                    "indexed_at",
                )
            )
            total_chunks += len(chunks)
        kb.status = ContactCenterKnowledgeBase.STATUS_READY
        kb.status_message = "Индекс актуален"
        kb.chunk_count = total_chunks
        kb.document_count = kb.documents.count()
        kb.last_reindexed_at = timezone.now()
        kb.save(
            update_fields=(
                "status",
                "status_message",
                "chunk_count",
                "document_count",
                "last_reindexed_at",
                "updated_at",
            )
        )
    except KnowledgeBaseError:
        kb.status = ContactCenterKnowledgeBase.STATUS_ERROR
        kb.save(update_fields=("status", "updated_at"))
        raise
    except ValueError as exc:
        kb.status = ContactCenterKnowledgeBase.STATUS_ERROR
        kb.status_message = str(exc)[:500]
        kb.save(update_fields=("status", "status_message", "updated_at"))
        raise KnowledgeBaseError(kb.status_message) from exc

    return serialize_knowledge_base(kb, include_documents=True)
