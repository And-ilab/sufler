"""HTTP API for contact-center sufler suggestions and internal KC test dialog."""

from __future__ import annotations

import json
from typing import Any, Mapping

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from auth.decorators import require_permissions
from auth.roles import (
    PERM_CC_TEST_DIALOG,
    PERM_SUFLER_CHAT,
    PERM_SUFLER_TELEPHONY,
)
from orchestrator.sufler import SuflerOrchestratorError, suggest
from orchestrator.test_dialog import run_test_prompt


def _parse_suggest_body(body: bytes) -> tuple[str, int, str]:
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise SuflerOrchestratorError(
            "Request body must be valid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SuflerOrchestratorError("Request body must be a JSON object")
    text = payload.get("text", payload.get("query"))
    if not isinstance(text, str) or not text.strip():
        raise SuflerOrchestratorError("text must be a non-empty string")
    limit: Any = payload.get("limit", 5)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise SuflerOrchestratorError("limit must be an integer")
    history = payload.get("client_history", payload.get("history", ""))
    if history is None:
        history = ""
    if not isinstance(history, str):
        raise SuflerOrchestratorError("client_history must be a string")
    return text, limit, history


@require_http_methods(["POST"])
@require_permissions(
    PERM_SUFLER_TELEPHONY,
    PERM_SUFLER_CHAT,
    require_all=False,
    api=True,
)
def sufler_suggest(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/sufler/suggest — FR-CC-03 / FR-CC-14."""
    try:
        text, limit, client_history = _parse_suggest_body(request.body)
        result = suggest(
            text,
            limit=limit,
            request_id=getattr(request, "audit_request_id", None),
            client_history=client_history,
        )
    except SuflerOrchestratorError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"request": [str(exc)]},
            },
            status=400,
        )
    except ValueError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"request": [str(exc)]},
            },
            status=400,
        )
    response = JsonResponse(result)
    response["X-Request-ID"] = result["request_id"]
    return response


def _parse_test_dialog_body(body: bytes) -> tuple[str, str, bool]:
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise SuflerOrchestratorError(
            "Request body must be valid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SuflerOrchestratorError("Request body must be a JSON object")
    text = payload.get("text", payload.get("query"))
    if not isinstance(text, str) or not text.strip():
        raise SuflerOrchestratorError("text must be a non-empty string")
    scenario_id = payload.get("scenario_id", "CC-SCR-008")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise SuflerOrchestratorError("scenario_id must be a non-empty string")
    use_pipeline = payload.get("use_pipeline", True)
    if not isinstance(use_pipeline, bool):
        raise SuflerOrchestratorError("use_pipeline must be a boolean")
    return text, scenario_id, use_pipeline


@require_http_methods(["POST"])
@require_permissions(PERM_CC_TEST_DIALOG, api=True)
def sufler_test_dialog(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/sufler/test-dialog — II.3.5.5 / SUF-T-06."""
    try:
        text, scenario_id, use_pipeline = _parse_test_dialog_body(request.body)
        result = run_test_prompt(
            text,
            scenario_id=scenario_id,
            use_pipeline=use_pipeline,
            request_id=getattr(request, "audit_request_id", None),
        )
    except SuflerOrchestratorError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"request": [str(exc)]},
            },
            status=400,
        )
    response = JsonResponse(result)
    if result.get("request_id"):
        response["X-Request-ID"] = str(result["request_id"])
    return response
