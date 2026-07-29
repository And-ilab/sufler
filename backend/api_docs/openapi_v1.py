"""OpenAPI 3 documentation for integrator-facing v1 APIs (приёмка / Postman)."""

from __future__ import annotations

from typing import Any


def build_openapi_v1() -> dict[str, Any]:
    """Curated OpenAPI covering assistant, sufler, and ingest (knowledge) APIs."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Sufler AI Hub API",
            "description": (
                "Integrator-facing OpenAPI for приёмка and Postman. "
                "Covers `/api/v1/assistant` (III.7 / III.10.2), "
                "`/api/v1/sufler` (FR-CC-03 / II.3.5.5), and "
                "`/api/v1/knowledge` (SUZ ingest INT-01…09)."
            ),
            "version": "1.0.0",
            "contact": {"name": "ООО «ГС Ритейл» · договор № 14-03/2026"},
        },
        "servers": [
            {"url": "http://127.0.0.1:8000", "description": "Local Django"},
            {"url": "/", "description": "Same origin"},
        ],
        "tags": [
            {"name": "assistant", "description": "ИИ-ассистент chat + FR-RPT-ASS"},
            {"name": "sufler", "description": "Суфлёр suggest + internal KC test-dialog"},
            {"name": "ingest", "description": "СУЗ Model B webhook + INT-09 reconcile"},
        ],
        "paths": {
            **_assistant_paths(),
            **_sufler_paths(),
            **_ingest_paths(),
        },
        "components": {
            "securitySchemes": {
                "SessionCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "sessionid",
                    "description": "Django session after POST /api/auth/login/",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Optional bearer token (future / gateway)",
                },
                "SuzHmac": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Sufler-Signature",
                    "description": "HMAC-SHA256(raw_body, SUZ_WEBHOOK_HMAC_SECRET)",
                },
            },
            "schemas": _schemas(),
        },
    }


def _error_responses(*codes: int) -> dict[str, Any]:
    mapping = {
        400: "Validation error",
        401: "Authentication required / HMAC failed",
        403: "Missing RBAC permission",
        503: "Temporary / misconfigured",
    }
    return {
        str(code): {
            "description": mapping.get(code, "Error"),
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }
            },
        }
        for code in codes
    }


def _assistant_paths() -> dict[str, Any]:
    session_security = [{"SessionCookie": []}, {"BearerAuth": []}]
    return {
        "/api/v1/assistant/chat": {
            "post": {
                "tags": ["assistant"],
                "operationId": "assistantChatStream",
                "summary": "Stream assistant reply (SSE)",
                "description": (
                    "OpenAI-compatible SSE from ModelGateway profile "
                    "`assistant_bank`. Requires `assistant.use`."
                ),
                "security": session_security,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/AssistantChatRequest"
                            },
                            "example": {
                                "message": "Нужна справка о вкладе",
                                "session_id": "sess-demo-1",
                                "stream": True,
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "SSE token stream (text/event-stream)",
                        "headers": {
                            "X-Assistant-Profile": {
                                "schema": {
                                    "type": "string",
                                    "enum": ["assistant_bank"],
                                }
                            },
                            "X-Session-ID": {"schema": {"type": "string"}},
                            "X-Request-ID": {"schema": {"type": "string"}},
                        },
                        "content": {
                            "text/event-stream": {
                                "schema": {"type": "string"}
                            }
                        },
                    },
                    **_error_responses(400, 401, 403),
                },
            }
        },
        "/api/v1/assistant/reports/": {
            "get": {
                "tags": ["assistant"],
                "operationId": "assistantReportsCatalog",
                "summary": "FR-RPT-ASS catalog",
                "security": session_security,
                "responses": {
                    "200": {
                        "description": "Catalog FR-RPT-ASS-01…08",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    **_error_responses(403),
                },
            }
        },
        "/api/v1/assistant/reports/analytics/": {
            "get": {
                "tags": ["assistant"],
                "operationId": "assistantReportsAnalytics",
                "summary": "Assistant usage / feedback analytics",
                "security": session_security,
                "parameters": [
                    {
                        "name": "date_from",
                        "in": "query",
                        "schema": {"type": "string", "format": "date"},
                    },
                    {
                        "name": "date_to",
                        "in": "query",
                        "schema": {"type": "string", "format": "date"},
                    },
                    {
                        "name": "department",
                        "in": "query",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Analytics payload",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    **_error_responses(400, 403),
                },
            }
        },
        "/api/v1/assistant/reports/export/": {
            "get": {
                "tags": ["assistant"],
                "operationId": "assistantReportsExport",
                "summary": "Export analytics CSV/XLSX (FR-RPT-ASS-07)",
                "security": session_security,
                "parameters": [
                    {
                        "name": "format",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["csv", "xlsx"],
                            "default": "csv",
                        },
                    },
                    {
                        "name": "date_from",
                        "in": "query",
                        "schema": {"type": "string", "format": "date"},
                    },
                    {
                        "name": "date_to",
                        "in": "query",
                        "schema": {"type": "string", "format": "date"},
                    },
                ],
                "responses": {
                    "200": {"description": "CSV or XLSX attachment"},
                    **_error_responses(400, 403),
                },
            }
        },
        "/api/v1/assistant/reports/{report_id}/": {
            "get": {
                "tags": ["assistant"],
                "operationId": "assistantReportDetail",
                "summary": "Single FR-RPT-ASS section",
                "security": session_security,
                "parameters": [
                    {
                        "name": "report_id",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "pattern": "^FR-RPT-ASS-0[1-8]$",
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Report section payload",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    **_error_responses(400, 403),
                },
            }
        },
    }


def _sufler_paths() -> dict[str, Any]:
    session_security = [{"SessionCookie": []}, {"BearerAuth": []}]
    return {
        "/api/v1/sufler/suggest": {
            "post": {
                "tags": ["sufler"],
                "operationId": "suflerSuggest",
                "summary": "Ranked operator hints (FR-CC-03 / FR-CC-14)",
                "description": (
                    "Requires `sufler.telephony` or `sufler.chat`. "
                    "Returns hints with %% relevance and SUZ citations."
                ),
                "security": session_security,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SuflerSuggestRequest"
                            },
                            "example": {
                                "text": "как оформить дебетовую карту",
                                "limit": 5,
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Hints payload",
                        "headers": {
                            "X-Request-ID": {"schema": {"type": "string"}}
                        },
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/SuflerSuggestResponse"
                                }
                            }
                        },
                    },
                    **_error_responses(400, 401, 403),
                },
            }
        },
        "/api/v1/sufler/test-dialog": {
            "post": {
                "tags": ["sufler"],
                "operationId": "suflerTestDialog",
                "summary": "Internal KC test-dialog (II.3.5.5)",
                "security": session_security,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SuflerTestDialogRequest"
                            },
                            "example": {
                                "text": "Какие документы для вклада?",
                                "scenario_id": "CC-SCR-008",
                                "use_pipeline": True,
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "LLM reply + relevance",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    **_error_responses(400, 401, 403),
                },
            }
        },
    }


def _ingest_paths() -> dict[str, Any]:
    return {
        "/api/v1/knowledge/events": {
            "post": {
                "tags": ["ingest"],
                "operationId": "suzKnowledgeEvents",
                "summary": "SUZ Model B webhook (INT-01…05, INT-07)",
                "description": (
                    "HMAC required when `SUZ_WEBHOOK_HMAC_SECRET` is set. "
                    "In `SUZ_INGEST_MODE=prod` the secret is mandatory."
                ),
                "security": [{"SuzHmac": []}],
                "parameters": [
                    {
                        "name": "X-Sufler-Event-Id",
                        "in": "header",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Must match body event_id when present",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SuzEventPayload"
                            }
                        }
                    },
                },
                "responses": {
                    "202": {
                        "description": "Accepted and queued",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/SuzEventAccepted"
                                }
                            }
                        },
                    },
                    **_error_responses(400, 401, 503),
                },
            }
        },
        "/api/v1/knowledge/reconcile/": {
            "get": {
                "tags": ["ingest"],
                "operationId": "suzReconcileStatus",
                "summary": "INT-09 reconcile cursor status",
                "responses": {
                    "200": {
                        "description": "Cursor / last run metadata",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/knowledge/reconcile/run/": {
            "post": {
                "tags": ["ingest"],
                "operationId": "suzReconcileRun",
                "summary": "Trigger INT-09 Bitrix changes poll",
                "parameters": [
                    {
                        "name": "async",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["0", "1", "true", "false"],
                        },
                        "description": "Queue Celery task when 1/true",
                    }
                ],
                "responses": {
                    "200": {"description": "Synchronous reconcile result"},
                    "202": {"description": "Queued async task"},
                    **_error_responses(403, 502, 503),
                },
            }
        },
    }


def _schemas() -> dict[str, Any]:
    return {
        "Error": {
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {"type": "string"},
                "details": {"type": "object"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "detail": {"type": "string"},
                "required_permissions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "AssistantChatMessage": {
            "type": "object",
            "required": ["role", "content"],
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["system", "user", "assistant", "tool"],
                },
                "content": {"type": "string"},
            },
        },
        "AssistantChatRequest": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "messages": {
                    "type": "array",
                    "items": {
                        "$ref": "#/components/schemas/AssistantChatMessage"
                    },
                },
                "session_id": {"type": "string"},
                "stream": {"type": "boolean", "default": True},
            },
        },
        "SuflerSuggestRequest": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "query": {
                    "type": "string",
                    "description": "Alias for text",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
        },
        "SuflerCitation": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "permalink": {"type": "string", "format": "uri"},
            },
        },
        "SuflerHint": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "relevance": {"type": "number"},
                "citations": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/SuflerCitation"},
                },
            },
        },
        "SuflerSuggestResponse": {
            "type": "object",
            "properties": {
                "kb_id": {"type": "string", "example": "cc_production"},
                "hints": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/SuflerHint"},
                },
                "request_id": {"type": "string"},
                "latency_ms": {"type": "object"},
            },
        },
        "SuflerTestDialogRequest": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "scenario_id": {
                    "type": "string",
                    "default": "CC-SCR-008",
                },
                "use_pipeline": {"type": "boolean", "default": True},
            },
        },
        "SuzEventPayload": {
            "type": "object",
            "description": "SUZ Model B event (see ingest README / tz-bitrix-rag)",
            "properties": {
                "event_id": {"type": "string"},
                "event_type": {"type": "string"},
                "article_id": {"type": "integer"},
                "iblock_id": {"type": "integer"},
                "checksum": {"type": "string"},
                "body_plain": {"type": "string"},
                "body_html": {"type": "string"},
            },
        },
        "SuzEventAccepted": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["accepted"]},
                "event_id": {"type": "string"},
                "outcome": {"type": "string", "enum": ["queued"]},
                "task_id": {"type": "string"},
                "ingest_mode": {"type": "string"},
            },
        },
    }


def merge_into_spectacular_schema(
    result: dict[str, Any],
    **_kwargs: Any,
) -> dict[str, Any]:
    """drf-spectacular POSTPROCESSING_HOOK: inject curated v1 paths."""
    curated = build_openapi_v1()
    paths = result.setdefault("paths", {})
    paths.update(curated["paths"])

    components = result.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.update(curated["components"]["schemas"])
    security = components.setdefault("securitySchemes", {})
    security.update(curated["components"]["securitySchemes"])

    existing_tags = {tag.get("name") for tag in result.get("tags") or []}
    tags = list(result.get("tags") or [])
    for tag in curated["tags"]:
        if tag["name"] not in existing_tags:
            tags.append(tag)
    result["tags"] = tags

    info = result.setdefault("info", {})
    info.setdefault("title", curated["info"]["title"])
    if not info.get("description"):
        info["description"] = curated["info"]["description"]
    info.setdefault("version", curated["info"]["version"])
    return result
