from __future__ import annotations

import json
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from audit import emit_kb_change
from auth.decorators import (
    permission_denied_response,
    require_permissions,
    roles_required,
)
from auth.roles import PERM_QU_ADMIN, role_codes_for_user
from hub.model_registry_store import (
    get_model_settings,
    serialize_model_settings,
    update_model_settings,
)
from qu.service import preview_query


ADMIN_ROLES = (
    "software_administrator",
    "llm_knowledge_base_administrator",
    "contact_center_module_administrator",
    "ai_assistant_module_administrator",
    "document_recognition_module_administrator",
)
PROFILE_ROLES = {
    "assistant_bank": {
        "software_administrator",
        "llm_knowledge_base_administrator",
        "ai_assistant_module_administrator",
    },
    "sufler_cc": {
        "software_administrator",
        "contact_center_module_administrator",
    },
}


def _profile(request: HttpRequest) -> str:
    profile = request.GET.get("profile", "")
    if profile not in PROFILE_ROLES:
        raise ValueError("profile must be assistant_bank or sufler_cc")
    return profile


def _check_profile_access(
    request: HttpRequest,
    profile: str,
) -> JsonResponse | None:
    if role_codes_for_user(request.user).intersection(PROFILE_ROLES[profile]):
        return None
    return permission_denied_response(
        request,
        required=(f"model_registry:{profile}",),
        force_json=True,
    )


def _parse_update_payload(request: HttpRequest) -> dict[str, Any]:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON") from exc
    if not isinstance(body, Mapping):
        raise ValueError("Request body must be a JSON object")
    generation = body.get("generation", {})
    rag = body.get("rag", {})
    if not isinstance(generation, Mapping) or not isinstance(rag, Mapping):
        raise ValueError("generation and rag must be JSON objects")
    allowed_root = {"generation", "rag"}
    unknown_root = set(body) - allowed_root
    if unknown_root:
        raise ValueError(
            f"Unknown sections: {', '.join(sorted(unknown_root))}"
        )
    generation_fields = {
        "temperature",
        "top_p",
        "max_tokens",
        "response_chars_max",
    }
    rag_fields = {
        "chunk_size_tokens",
        "chunk_overlap_tokens",
        "context_inclusion",
        "deterministic_answer",
    }
    for section_name, section, fields in (
        ("generation", generation, generation_fields),
        ("rag", rag, rag_fields),
    ):
        missing = fields - set(section)
        unknown = set(section) - fields
        if missing:
            raise ValueError(
                f"{section_name} is missing: {', '.join(sorted(missing))}"
            )
        if unknown:
            raise ValueError(
                f"{section_name} has unknown fields: "
                f"{', '.join(sorted(unknown))}"
            )
    return {
        **generation,
        "chunk_size_tokens": rag.get("chunk_size_tokens"),
        "chunk_overlap_tokens": rag.get("chunk_overlap_tokens"),
        "context_inclusion_threshold": rag.get("context_inclusion"),
        "deterministic_answer_threshold": rag.get(
            "deterministic_answer"
        ),
    }


@require_http_methods(["GET", "PUT"])
@roles_required(*ADMIN_ROLES, api=True)
def model_params(request: HttpRequest) -> JsonResponse:
    try:
        profile = _profile(request)
    except ValueError as exc:
        return JsonResponse(
            {"error": "validation_error", "details": {"profile": [str(exc)]}},
            status=400,
        )
    denied = _check_profile_access(request, profile)
    if denied is not None:
        return denied

    try:
        if request.method == "PUT":
            payload = _parse_update_payload(request)
            instance = update_model_settings(
                profile,
                payload,
                username=request.user.get_username(),
            )
            emit_kb_change(
                request=request,
                profile=profile,
                revision=instance.revision,
                changed_fields=payload.keys(),
            )
        else:
            instance = get_model_settings(profile)
    except ValidationError as exc:
        details = getattr(exc, "message_dict", {"form": exc.messages})
        return JsonResponse(
            {"error": "validation_error", "details": details},
            status=400,
        )
    except (TypeError, ValueError) as exc:
        return JsonResponse(
            {"error": "validation_error", "details": {"form": [str(exc)]}},
            status=400,
        )

    return JsonResponse(serialize_model_settings(instance))


@require_http_methods(["POST"])
@require_permissions(PERM_QU_ADMIN, api=True)
def qu_preview(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, Mapping):
            raise ValueError("Request body must be a JSON object")
        query = body.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        limit = body.get("limit", 5)
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        result = preview_query(query, limit=limit)
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"body": ["Request body must be valid JSON"]},
            },
            status=400,
        )
    except ValueError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"query": [str(exc)]},
            },
            status=400,
        )
    return JsonResponse(result)
