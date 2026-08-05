"""Assistant admin stubs: assistant_* KB, prompts CRUD, tools registry (III.6)."""

from __future__ import annotations

import re
from typing import Any, Mapping

from django.db import transaction
from django.utils.text import slugify

from hub.models import (
    AssistantCapability,
    AssistantKnowledgeBase,
    AssistantPromptTemplate,
)

FORBIDDEN_KB_SLUGS = frozenset({"cc_production", "cc-production", "suz_cc"})
ASSISTANT_SLUG_PREFIX = "assistant_"
SLUG_RE = re.compile(r"^[a-z0-9_]+$")

DEFAULT_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "code": "rag_kb",
        "name": "Поиск по KB (RAG)",
        "description": "Retrieval по индексам assistant_* (не cc_production).",
        "deep_link": "kb_admin",
        "category": "rag",
        "sort_order": 10,
        "enabled": True,
    },
    {
        "code": "external_sources",
        "name": "Внешние источники",
        "description": "Secure adapters / whitelist источников (VII.5 D4).",
        "deep_link": "data_sources",
        "category": "integration",
        "sort_order": 20,
        "enabled": True,
    },
    {
        "code": "generate_document",
        "name": "Генерация документов",
        "description": "Word/PDF по шаблону.",
        "deep_link": "assistant_tools",
        "category": "tool",
        "sort_order": 30,
        "enabled": True,
    },
    {
        "code": "rpa",
        "name": "RPA",
        "description": "Whitelist сценариев с confirm (VII.5 D4).",
        "deep_link": "assistant_tools",
        "category": "tool",
        "sort_order": 40,
        "enabled": False,
    },
    {
        "code": "sql_code",
        "name": "SQL / код",
        "description": "Read-only SQL и sandbox кода (III.6.5).",
        "deep_link": "assistant_tools",
        "category": "tool",
        "sort_order": 50,
        "enabled": False,
    },
    {
        "code": "summarize",
        "name": "Саммаризация файлов",
        "description": "Аудио/видео/документы.",
        "deep_link": "capabilities",
        "category": "tool",
        "sort_order": 60,
        "enabled": True,
    },
    {
        "code": "translate",
        "name": "Перевод RU↔EN",
        "description": "Двуязычный ответ, не формат файла.",
        "deep_link": "prompts_assistant",
        "category": "tool",
        "sort_order": 70,
        "enabled": True,
    },
    {
        "code": "clarify",
        "name": "Уточняющие вопросы",
        "description": "Низкая релевантность → уточнение.",
        "deep_link": "qu_admin",
        "category": "qu",
        "sort_order": 80,
        "enabled": True,
    },
)

DEFAULT_PROMPTS: tuple[dict[str, Any], ...] = (
    {
        "name": "System · assistant_bank",
        "prompt_type": AssistantPromptTemplate.TYPE_SYSTEM,
        "scope": "bank",
        "body": (
            "Ты внутренний ИИ-ассистент банка. Отвечай только на основе "
            "индексов {{kb}} и контекста подразделения {{dept}}. "
            "Пользователь: {{user}}."
        ),
        "status": AssistantPromptTemplate.STATUS_PUBLISHED,
        "kb_slug": "assistant_hr",
    },
    {
        "name": "Task · оформление отпуска",
        "prompt_type": AssistantPromptTemplate.TYPE_TASK,
        "scope": "department",
        "body": (
            "Сформулируй пошаговый ответ по регламенту отпусков. "
            "Укажи сроки и необходимые согласования."
        ),
        "status": AssistantPromptTemplate.STATUS_DRAFT,
        "kb_slug": "assistant_hr",
    },
    {
        "name": "Scope · ИБ",
        "prompt_type": AssistantPromptTemplate.TYPE_SCOPE,
        "scope": "security",
        "body": "Не раскрывай внутренние политики ИБ вне AD-scope пользователя.",
        "status": AssistantPromptTemplate.STATUS_PUBLISHED,
        "kb_slug": "assistant_security",
    },
)

DEFAULT_KBS: tuple[dict[str, str], ...] = (
    {
        "name": "HR policies",
        "slug": "assistant_hr",
        "scope": "hr",
        "description": "Корпоративные регламенты HR",
    },
    {
        "name": "IT runbooks",
        "slug": "assistant_it",
        "scope": "it",
        "description": "ИТ-инструкции и доступы",
    },
    {
        "name": "Security & compliance",
        "slug": "assistant_security",
        "scope": "security",
        "description": "Политики ИБ",
    },
)


class AssistantAdminError(ValueError):
    """Invalid assistant admin operation."""


def ensure_assistant_seed(username: str = "system") -> None:
    """Idempotent seed for stub admin screens.

    Knowledge bases are NOT auto-created — the assistant chat catalog must
    mirror real Hub data (empty DB → empty dropdown).
    """
    if not AssistantPromptTemplate.objects.exists():
        for item in DEFAULT_PROMPTS:
            AssistantPromptTemplate.objects.create(
                name=item["name"],
                prompt_type=item["prompt_type"],
                scope=item["scope"],
                body=item["body"],
                status=item["status"],
                kb_slug=item["kb_slug"],
                updated_by=username,
            )
    for item in DEFAULT_CAPABILITIES:
        AssistantCapability.objects.get_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "description": item["description"],
                "deep_link": item["deep_link"],
                "category": item["category"],
                "sort_order": item["sort_order"],
                "enabled": item["enabled"],
            },
        )


def _normalize_assistant_slug(raw: str) -> str:
    value = (raw or "").strip().lower().replace("-", "_")
    if value in FORBIDDEN_KB_SLUGS or value == "cc_production":
        raise AssistantAdminError(
            "assistant KB must not use cc_production namespace"
        )
    if not value.startswith(ASSISTANT_SLUG_PREFIX):
        value = f"{ASSISTANT_SLUG_PREFIX}{slugify(value, allow_unicode=False) or 'kb'}"
    value = value.replace("-", "_")
    if not SLUG_RE.match(value):
        raise AssistantAdminError("slug must be snake_case assistant_*")
    if value in FORBIDDEN_KB_SLUGS:
        raise AssistantAdminError(
            "assistant KB must not use cc_production namespace"
        )
    return value


def serialize_kb(kb: AssistantKnowledgeBase) -> dict[str, Any]:
    return {
        "id": kb.pk,
        "name": kb.name,
        "slug": kb.slug,
        "namespace": "assistant_*",
        "isolated_from": "cc_production",
        "scope": kb.scope,
        "description": kb.description,
        "status": kb.status,
        "document_count": kb.document_count,
        "created_at": kb.created_at.isoformat(),
        "updated_at": kb.updated_at.isoformat(),
        "created_by": kb.created_by,
    }


def serialize_prompt(prompt: AssistantPromptTemplate) -> dict[str, Any]:
    return {
        "id": prompt.pk,
        "name": prompt.name,
        "prompt_type": prompt.prompt_type,
        "scope": prompt.scope,
        "body": prompt.body,
        "status": prompt.status,
        "version": prompt.version,
        "kb_slug": prompt.kb_slug,
        "updated_by": prompt.updated_by,
        "created_at": prompt.created_at.isoformat(),
        "updated_at": prompt.updated_at.isoformat(),
    }


def serialize_capability(item: AssistantCapability) -> dict[str, Any]:
    return {
        "id": item.pk,
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "enabled": item.enabled,
        "deep_link": item.deep_link,
        "category": item.category,
        "sort_order": item.sort_order,
        "updated_at": item.updated_at.isoformat(),
    }


def list_assistant_kbs(*, seed: bool = False) -> list[dict[str, Any]]:
    """Return assistant_* KBs. Do not invent stub rows unless seed=True (tests/demo)."""
    if seed:
        ensure_assistant_seed()
    return [serialize_kb(item) for item in AssistantKnowledgeBase.objects.all()]


def create_assistant_kb(
    payload: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise AssistantAdminError("name is required")
    slug_raw = str(payload.get("slug") or name)
    slug = _normalize_assistant_slug(slug_raw)
    if AssistantKnowledgeBase.objects.filter(slug=slug).exists():
        raise AssistantAdminError(f"KB {slug!r} already exists")
    if AssistantKnowledgeBase.objects.filter(name=name).exists():
        raise AssistantAdminError("name must be unique")
    kb = AssistantKnowledgeBase.objects.create(
        name=name,
        slug=slug,
        scope=str(payload.get("scope") or "department")[:64],
        description=str(payload.get("description") or ""),
        status=AssistantKnowledgeBase.STATUS_READY,
        created_by=username,
    )
    return serialize_kb(kb)


def delete_assistant_kb(kb_id: int) -> None:
    try:
        kb = AssistantKnowledgeBase.objects.get(pk=kb_id)
    except AssistantKnowledgeBase.DoesNotExist as exc:
        raise AssistantAdminError("KB not found") from exc
    if not kb.slug.startswith(ASSISTANT_SLUG_PREFIX):
        raise AssistantAdminError("refusing to delete non-assistant namespace")
    kb.delete()


def list_prompts() -> list[dict[str, Any]]:
    ensure_assistant_seed()
    return [
        serialize_prompt(item)
        for item in AssistantPromptTemplate.objects.all()
    ]


def get_prompt(prompt_id: int) -> dict[str, Any]:
    try:
        return serialize_prompt(AssistantPromptTemplate.objects.get(pk=prompt_id))
    except AssistantPromptTemplate.DoesNotExist as exc:
        raise AssistantAdminError("prompt not found") from exc


def create_prompt(
    payload: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not name or not body:
        raise AssistantAdminError("name and body are required")
    prompt_type = str(payload.get("prompt_type") or "task")
    if prompt_type not in {
        AssistantPromptTemplate.TYPE_SYSTEM,
        AssistantPromptTemplate.TYPE_TASK,
        AssistantPromptTemplate.TYPE_SCOPE,
    }:
        raise AssistantAdminError("prompt_type must be system|task|scope")
    kb_slug = str(payload.get("kb_slug") or "").strip()
    if kb_slug:
        kb_slug = _normalize_assistant_slug(kb_slug)
    prompt = AssistantPromptTemplate.objects.create(
        name=name,
        prompt_type=prompt_type,
        scope=str(payload.get("scope") or "bank")[:64],
        body=body,
        status=AssistantPromptTemplate.STATUS_DRAFT,
        kb_slug=kb_slug,
        updated_by=username,
    )
    return serialize_prompt(prompt)


def update_prompt(
    prompt_id: int,
    payload: Mapping[str, Any],
    *,
    username: str,
) -> dict[str, Any]:
    try:
        prompt = AssistantPromptTemplate.objects.get(pk=prompt_id)
    except AssistantPromptTemplate.DoesNotExist as exc:
        raise AssistantAdminError("prompt not found") from exc

    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise AssistantAdminError("name cannot be empty")
        prompt.name = name
    if "body" in payload:
        body = str(payload.get("body") or "").strip()
        if not body:
            raise AssistantAdminError("body cannot be empty")
        prompt.body = body
    if "prompt_type" in payload:
        prompt_type = str(payload.get("prompt_type") or "")
        if prompt_type not in {
            AssistantPromptTemplate.TYPE_SYSTEM,
            AssistantPromptTemplate.TYPE_TASK,
            AssistantPromptTemplate.TYPE_SCOPE,
        }:
            raise AssistantAdminError("prompt_type must be system|task|scope")
        prompt.prompt_type = prompt_type
    if "scope" in payload:
        prompt.scope = str(payload.get("scope") or "bank")[:64]
    if "kb_slug" in payload:
        kb_slug = str(payload.get("kb_slug") or "").strip()
        prompt.kb_slug = _normalize_assistant_slug(kb_slug) if kb_slug else ""
    if "status" in payload:
        status = str(payload.get("status") or "")
        if status not in {
            AssistantPromptTemplate.STATUS_DRAFT,
            AssistantPromptTemplate.STATUS_PUBLISHED,
        }:
            raise AssistantAdminError("status must be draft|published")
        if (
            status == AssistantPromptTemplate.STATUS_PUBLISHED
            and prompt.status != AssistantPromptTemplate.STATUS_PUBLISHED
        ):
            prompt.version += 1
        prompt.status = status

    prompt.updated_by = username
    prompt.save()
    return serialize_prompt(prompt)


def delete_prompt(prompt_id: int) -> None:
    deleted, _ = AssistantPromptTemplate.objects.filter(pk=prompt_id).delete()
    if not deleted:
        raise AssistantAdminError("prompt not found")


def list_capabilities() -> list[dict[str, Any]]:
    ensure_assistant_seed()
    return [
        serialize_capability(item)
        for item in AssistantCapability.objects.all()
    ]


@transaction.atomic
def update_capability(
    code: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_assistant_seed()
    try:
        item = AssistantCapability.objects.select_for_update().get(code=code)
    except AssistantCapability.DoesNotExist as exc:
        raise AssistantAdminError("capability not found") from exc
    if "enabled" in payload:
        if not isinstance(payload.get("enabled"), bool):
            raise AssistantAdminError("enabled must be a boolean")
        item.enabled = bool(payload["enabled"])
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if name:
            item.name = name
    if "description" in payload:
        item.description = str(payload.get("description") or "")
    item.save()
    return serialize_capability(item)
