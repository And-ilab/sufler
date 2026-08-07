"""Proxy to host-side local LLM manager (model switcher)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

FALLBACK_CATALOG: dict[str, Any] = {
    "default_model_id": "qwen2.5-3b-instruct",
    "openai_alias": "qwen2.5-1.5b-instruct",
    "models": [
        {
            "id": "qwen2.5-3b-instruct",
            "label": "Qwen2.5 3B — качество",
            "description": "Медленнее на CPU, ответы точнее",
            "available": True,
        },
        {
            "id": "qwen2.5-1.5b-instruct",
            "label": "Qwen2.5 1.5B — быстрее",
            "description": "Быстрее на CPU, чуть проще ответы",
            "available": True,
        },
    ],
}


def manager_base_url() -> str:
    return (
        os.environ.get("LOCAL_LLM_MANAGER_URL")
        or "http://llm:8070"
    ).rstrip("/")


def _timeout() -> float:
    raw = os.environ.get("LOCAL_LLM_MANAGER_TIMEOUT_SECONDS", "120")
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 120.0


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    url = f"{manager_base_url()}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout or _timeout()) as resp:
        raw = resp.read().decode("utf-8")
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise ValueError("Manager returned non-object JSON")
    return payload


def _catalog_from_repo() -> dict[str, Any] | None:
    env_path = os.environ.get("LOCAL_LLM_CATALOG_PATH")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    here = Path(__file__).resolve()
    candidates.append(
        here.parents[2] / "infra" / "local-inference" / "models.json"
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("models"), list):
            return data
    return None


def offline_status() -> dict[str, Any]:
    catalog = _catalog_from_repo() or FALLBACK_CATALOG
    models = []
    for item in catalog.get("models", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        models.append(
            {
                "id": item["id"],
                "label": item.get("label") or item["id"],
                "description": item.get("description") or "",
                "available": bool(item.get("available", True)),
            }
        )
    return {
        "active_model_id": None,
        "switching": False,
        "llama_running": False,
        "manager_reachable": False,
        "openai_alias": catalog.get("openai_alias"),
        "models": models,
        "last_error": (
            "LLM manager недоступен. Запустите "
            "infra/local-inference/start-llm-manager.ps1"
        ),
    }


def get_models_status() -> dict[str, Any]:
    try:
        payload = _request("GET", "/models", timeout=5.0)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        status = offline_status()
        status["last_error"] = f"{status['last_error']} ({exc})"
        return status
    payload["manager_reachable"] = True
    return payload


def select_model(model_id: str) -> dict[str, Any]:
    model_id = model_id.strip()
    if not model_id:
        raise ValueError("model_id is required")
    try:
        payload = _request(
            "PUT",
            "/models",
            body={"model_id": model_id},
            timeout=_timeout(),
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            parsed = {"error": "switch_failed", "details": detail}
        raise RuntimeError(parsed.get("details") or parsed.get("error") or detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "LLM manager недоступен. Запустите start-llm-manager.ps1"
        ) from exc
    payload["manager_reachable"] = True
    return payload
