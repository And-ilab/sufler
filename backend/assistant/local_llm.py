"""Status helper for local Ollama (OpenAI-compatible) — no custom switcher."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def ollama_base_url() -> str:
    """Native Ollama API root (not /v1)."""
    raw = (
        os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("LOCAL_LLM_MANAGER_URL")  # legacy alias
        or "http://ollama:11434"
    ).rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[: -len("/v1")]
    return raw


def openai_base_url() -> str:
    return (
        os.environ.get("OPENAI_BASE_URL") or f"{ollama_base_url()}/v1"
    ).rstrip("/")


def active_model_id() -> str:
    return (
        os.environ.get("OPENAI_MODEL")
        or os.environ.get("OLLAMA_MODEL")
        or ""
    ).strip()


def _timeout() -> float:
    raw = os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30")
    try:
        return max(3.0, float(raw))
    except ValueError:
        return 30.0


def _get_json(url: str, *, timeout: float | None = None) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout or _timeout()) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw or "{}")


def offline_status(*, error: str | None = None) -> dict[str, Any]:
    model = active_model_id() or None
    return {
        "active_model_id": model,
        "switching": False,
        "llama_running": False,
        "manager_reachable": False,
        "openai_alias": model,
        "models": (
            [
                {
                    "id": model,
                    "label": model,
                    "description": "Задана через OPENAI_MODEL / OLLAMA_MODEL",
                    "available": True,
                }
            ]
            if model
            else []
        ),
        "last_error": error
        or (
            "Ollama недоступна. Поднимите сервис: "
            "COMPOSE_PROFILES=cpu-inference docker compose "
            "-f docker-compose.yml -f local-inference/docker-compose.cpu.yml up -d ollama"
        ),
    }


def get_models_status() -> dict[str, Any]:
    base = ollama_base_url()
    try:
        payload = _get_json(f"{base}/api/tags", timeout=5.0)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
        return offline_status(error=f"Ollama недоступна ({exc})")

    models: list[dict[str, Any]] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if not isinstance(name, str) or not name.strip():
            continue
        models.append(
            {
                "id": name,
                "label": name,
                "description": "",
                "available": True,
            }
        )

    configured = active_model_id()
    active = configured or (models[0]["id"] if models else None)
    return {
        "active_model_id": active,
        "switching": False,
        "llama_running": True,
        "manager_reachable": True,
        "openai_alias": active,
        "models": models,
        "last_error": None
        if models
        else (
            "В Ollama нет скачанных моделей. Пример: "
            "docker compose exec ollama ollama pull qwen2.5:3b"
        ),
    }


def select_model(model_id: str) -> dict[str, Any]:
    """Model switching via UI is disabled — change OPENAI_MODEL and restart backend."""
    raise RuntimeError(
        "Переключение модели в UI отключено. "
        "Скачайте модель: docker compose exec ollama ollama pull <name>, "
        "задайте OPENAI_MODEL=<name> в infra/.env и перезапустите backend."
    )
