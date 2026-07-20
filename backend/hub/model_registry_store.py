from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from django.conf import settings
from django.db import transaction

from core.model_registry import DEFAULT_REGISTRY_PATH, ModelRegistry
from hub.models import ModelRegistrySettings


PROFILE_TO_SLOT = {
    ModelRegistrySettings.PROFILE_ASSISTANT: "llm_assistant_bank",
    ModelRegistrySettings.PROFILE_SUFLER_CC: "llm_sufler_cc",
}

EDITABLE_FIELDS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "response_chars_max",
        "chunk_size_tokens",
        "chunk_overlap_tokens",
        "context_inclusion_threshold",
        "deterministic_answer_threshold",
    }
)


def registry_path() -> Path:
    return Path(
        getattr(settings, "MODEL_REGISTRY_PATH", DEFAULT_REGISTRY_PATH)
    )


def defaults_for_profile(profile: str) -> dict[str, Any]:
    try:
        slot_name = PROFILE_TO_SLOT[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: {profile}") from exc

    registry = ModelRegistry.load(registry_path())
    slot = registry.get_slot(slot_name)
    knowledge_base = registry.get_profile("kb_cc_production")
    default_temperature = 0.2 if profile == "sufler_cc" else 0.35
    return {
        "temperature": slot.kpi.get("temperature", default_temperature),
        "top_p": slot.kpi.get("top_p", 0.9),
        "max_tokens": slot.kpi.get("max_tokens", 1024),
        "response_chars_max": slot.kpi["response_chars_max"],
        "chunk_size_tokens": knowledge_base.chunk_size_tokens,
        "chunk_overlap_tokens": knowledge_base.chunk_overlap_tokens,
        "context_inclusion_threshold": (
            knowledge_base.context_inclusion_threshold
        ),
        "deterministic_answer_threshold": (
            knowledge_base.deterministic_answer_threshold
        ),
    }


def get_model_settings(profile: str) -> ModelRegistrySettings:
    defaults = defaults_for_profile(profile)
    instance, _ = ModelRegistrySettings.objects.get_or_create(
        profile=profile,
        defaults=defaults,
    )
    return instance


@transaction.atomic
def update_model_settings(
    profile: str,
    payload: Mapping[str, Any],
    *,
    username: str,
) -> ModelRegistrySettings:
    unknown_fields = set(payload) - EDITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unknown fields: {fields}")

    get_model_settings(profile)
    instance = ModelRegistrySettings.objects.select_for_update().get(
        profile=profile
    )
    for field_name, value in payload.items():
        setattr(instance, field_name, value)
    instance.updated_by = username
    instance.revision += 1
    instance.save()
    return instance


def serialize_model_settings(instance: ModelRegistrySettings) -> dict[str, Any]:
    slot_name = PROFILE_TO_SLOT[instance.profile]
    slot = ModelRegistry.load(registry_path()).get_slot(slot_name)
    return {
        "profile": instance.profile,
        "slot": slot_name,
        "generation": {
            "temperature": instance.temperature,
            "top_p": instance.top_p,
            "max_tokens": instance.max_tokens,
            "response_chars_max": instance.response_chars_max,
        },
        "rag": {
            "chunk_size_tokens": instance.chunk_size_tokens,
            "chunk_overlap_tokens": instance.chunk_overlap_tokens,
            "context_inclusion": instance.context_inclusion_threshold,
            "deterministic_answer": (
                instance.deterministic_answer_threshold
            ),
        },
        "read_only": {
            "dev_model": slot.dev_model,
            "prod_candidate": slot.prod_candidate,
            "status": slot.status,
        },
        "constraints": {
            "temperature": {
                "min": 0.1 if instance.profile == "sufler_cc" else 0,
                "max": 0.25 if instance.profile == "sufler_cc" else 1,
                "step": 0.01,
            },
            "top_p": {"min": 0.01, "max": 1, "step": 0.01},
            "max_tokens": {"min": 1, "max": 32768},
            "response_chars_max": {"min": 1, "max": 500},
        },
        "revision": instance.revision,
        "updated_at": instance.updated_at.isoformat(),
        "updated_by": instance.updated_by,
    }
