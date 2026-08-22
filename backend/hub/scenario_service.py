"""CRUD and publish for dialog scenarios (FR-SCR-01…12)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from hub.models import DialogScenario, DialogScenarioVersion
from hub.scenario_catalog import DEFAULT_SYSTEM_PROMPT


class ScenarioAdminError(ValueError):
    """Invalid scenario payload."""


def _graph_nodes(graph: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    raw = (graph or {}).get("nodes")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def serialize_scenario(item: DialogScenario, *, include_graph: bool = False) -> dict[str, Any]:
    version = item.current_version
    payload: dict[str, Any] = {
        "code": item.code,
        "title": item.title,
        "root_question": item.root_question,
        "status": item.status,
        "channels": item.channels,
        "version_number": version.version_number if version else 0,
        "is_published": bool(version and version.is_published),
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        "updated_by": item.updated_by,
    }
    if include_graph:
        payload["graph"] = version.graph if version else {"nodes": []}
        payload["system_prompt"] = version.system_prompt if version else DEFAULT_SYSTEM_PROMPT
    return payload


def list_scenarios() -> dict[str, Any]:
    items = list(
        DialogScenario.objects.select_related("current_version").all()
    )
    published = sum(
        1 for item in items if item.status == DialogScenario.STATUS_PRODUCTION
    )
    return {
        "items": [serialize_scenario(item) for item in items],
        "counts": {
            "total": len(items),
            "production": published,
            "draft": len(items) - published,
        },
    }


def get_scenario(code: str) -> DialogScenario:
    key = (code or "").strip().upper()
    try:
        return DialogScenario.objects.select_related("current_version").get(code=key)
    except DialogScenario.DoesNotExist as exc:
        raise ScenarioAdminError(f"scenario {key} not found") from exc


def _clean_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if not code:
        raise ScenarioAdminError("code is required")
    if len(code) > 32:
        raise ScenarioAdminError("code is too long")
    return code


def _clean_graph(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"nodes": []}
    if not isinstance(raw, Mapping):
        raise ScenarioAdminError("graph must be an object")
    nodes = raw.get("nodes")
    if nodes is None:
        nodes = []
    if not isinstance(nodes, list):
        raise ScenarioAdminError("graph.nodes must be an array")
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise ScenarioAdminError(f"graph.nodes[{index}] must be an object")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise ScenarioAdminError(f"graph.nodes[{index}].id is required")
        if node_id in seen:
            raise ScenarioAdminError(f"duplicate node id: {node_id}")
        seen.add(node_id)
        edges_raw = node.get("edges") or []
        if not isinstance(edges_raw, list):
            raise ScenarioAdminError(f"node {node_id} edges must be an array")
        edges = []
        for edge in edges_raw:
            if not isinstance(edge, Mapping):
                continue
            target = str(edge.get("to") or "").strip()
            keywords = edge.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = []
            cleaned_keywords = [
                str(item).strip()
                for item in keywords
                if str(item).strip()
            ]
            dangerous = [item for item in cleaned_keywords if len(item) < 2]
            if dangerous:
                raise ScenarioAdminError(
                    f"node {node_id} has unsafe one-letter transition keyword"
                )
            edges.append(
                {
                    "to": target,
                    "label": str(edge.get("label") or "").strip(),
                    "reply": str(edge.get("reply") or "").strip(),
                    "keywords": cleaned_keywords,
                }
            )
        examples = node.get("examples") or []
        if not isinstance(examples, list):
            examples = []
        clean_node = {
                "id": node_id,
                "type": str(node.get("type") or "answer").strip() or "answer",
                "label": str(node.get("label") or node_id).strip(),
                "hint_text": str(node.get("hint_text") or "").strip(),
                "clarify_text": str(node.get("clarify_text") or "").strip(),
                "examples": [str(item).strip() for item in examples if str(item).strip()],
                "intent_id": str(node.get("intent_id") or "").strip(),
                "edges": edges,
            }
        position = node.get("position")
        if isinstance(position, Mapping):
            try:
                x = max(0.0, min(float(position.get("x", 0)), 10000.0))
                y = max(0.0, min(float(position.get("y", 0)), 10000.0))
                clean_node["position"] = {"x": round(x, 1), "y": round(y, 1)}
            except (TypeError, ValueError):
                pass
        cleaned.append(clean_node)
    return {"nodes": cleaned}


def backfill_missing_replies(
    graph: Mapping[str, Any] | None,
    catalog_graph: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], int]:
    """Copy catalog replies into matching edges without changing other data."""
    result = deepcopy(dict(graph or {}))
    catalog_nodes = {
        str(node.get("id") or ""): node
        for node in _graph_nodes(catalog_graph)
        if str(node.get("id") or "")
    }
    updated = 0
    for node in _graph_nodes(result):
        source_id = str(node.get("id") or "")
        catalog_node = catalog_nodes.get(source_id)
        if catalog_node is None:
            continue
        replies = {
            str(edge.get("to") or ""): str(edge.get("reply") or "").strip()
            for edge in catalog_node.get("edges") or []
            if isinstance(edge, Mapping)
            and str(edge.get("to") or "")
            and str(edge.get("reply") or "").strip()
        }
        for edge in node.get("edges") or []:
            if not isinstance(edge, dict) or str(edge.get("reply") or "").strip():
                continue
            reply = replies.get(str(edge.get("to") or ""))
            if reply:
                edge["reply"] = reply
                updated += 1
    return result, updated


def _next_version_number(scenario: DialogScenario) -> int:
    latest = scenario.versions.order_by("-version_number").first()
    return (latest.version_number + 1) if latest else 1


@transaction.atomic
def create_scenario(payload: Mapping[str, Any], *, username: str = "") -> dict[str, Any]:
    code = _clean_code(payload.get("code"))
    if DialogScenario.objects.filter(code=code).exists():
        raise ScenarioAdminError(f"scenario {code} already exists")
    title = str(payload.get("title") or code).strip()[:200]
    root = str(payload.get("root_question") or "").strip()[:500]
    channels = str(payload.get("channels") or DialogScenario.CHANNEL_BOTH).strip()
    if channels not in {
        DialogScenario.CHANNEL_BOTH,
        DialogScenario.CHANNEL_TELEPHONY,
        DialogScenario.CHANNEL_CHAT,
    }:
        raise ScenarioAdminError("channels must be both, telephony or online_chat")
    graph = _clean_graph(payload.get("graph"))
    prompt = str(payload.get("system_prompt") or DEFAULT_SYSTEM_PROMPT)
    item = DialogScenario.objects.create(
        code=code,
        title=title,
        root_question=root,
        status=DialogScenario.STATUS_DRAFT,
        channels=channels,
        updated_by=username,
    )
    version = DialogScenarioVersion.objects.create(
        scenario=item,
        version_number=1,
        graph=graph,
        system_prompt=prompt,
        created_by=username,
    )
    item.current_version = version
    item.save(update_fields=["current_version", "updated_at", "updated_by"])
    return serialize_scenario(item, include_graph=True)


@transaction.atomic
def update_scenario(
    code: str,
    payload: Mapping[str, Any],
    *,
    username: str = "",
    publish: bool = False,
) -> dict[str, Any]:
    item = get_scenario(code)
    if "title" in payload:
        title = str(payload.get("title") or "").strip()[:200]
        if not title:
            raise ScenarioAdminError("title is required")
        item.title = title
    if "root_question" in payload:
        item.root_question = str(payload.get("root_question") or "").strip()[:500]
    if "channels" in payload:
        channels = str(payload.get("channels") or "").strip()
        if channels not in {
            DialogScenario.CHANNEL_BOTH,
            DialogScenario.CHANNEL_TELEPHONY,
            DialogScenario.CHANNEL_CHAT,
        }:
            raise ScenarioAdminError("channels must be both, telephony or online_chat")
        item.channels = channels
    needs_version = "graph" in payload or "system_prompt" in payload or publish
    current = item.current_version
    graph = _clean_graph(payload["graph"]) if "graph" in payload else (
        current.graph if current else {"nodes": []}
    )
    prompt = (
        str(payload.get("system_prompt") or "").strip()
        if "system_prompt" in payload
        else (current.system_prompt if current else DEFAULT_SYSTEM_PROMPT)
    )
    if needs_version:
        if current and not current.is_published and not publish:
            current.graph = graph
            current.system_prompt = prompt
            current.created_by = username or current.created_by
            current.save()
            version = current
        else:
            version = DialogScenarioVersion.objects.create(
                scenario=item,
                version_number=_next_version_number(item),
                graph=graph,
                system_prompt=prompt,
                created_by=username,
            )
            item.current_version = version
        if publish:
            version.is_published = True
            version.published_at = timezone.now()
            version.save(update_fields=["is_published", "published_at"])
            item.status = DialogScenario.STATUS_PRODUCTION
    item.updated_by = username
    item.save()
    return serialize_scenario(item, include_graph=True)


@transaction.atomic
def upsert_from_catalog(payload: Mapping[str, Any], *, username: str = "seed") -> DialogScenario:
    code = _clean_code(payload.get("code"))
    title = str(payload.get("title") or code).strip()[:200]
    root = str(payload.get("root_question") or "").strip()[:500]
    status = str(payload.get("status") or DialogScenario.STATUS_DRAFT)
    channels = str(payload.get("channels") or DialogScenario.CHANNEL_BOTH)
    graph = _clean_graph(payload.get("graph"))
    prompt = str(payload.get("system_prompt") or DEFAULT_SYSTEM_PROMPT)
    item, _created = DialogScenario.objects.get_or_create(
        code=code,
        defaults={
            "title": title,
            "root_question": root,
            "status": DialogScenario.STATUS_DRAFT,
            "channels": channels,
            "updated_by": username,
        },
    )
    item.title = title
    item.root_question = root
    item.channels = channels
    item.updated_by = username
    current = item.current_version
    if current and not current.is_published:
        current.graph = graph
        current.system_prompt = prompt
        current.created_by = username
        current.save()
        version = current
    else:
        version = DialogScenarioVersion.objects.create(
            scenario=item,
            version_number=_next_version_number(item),
            graph=graph,
            system_prompt=prompt,
            created_by=username,
        )
        item.current_version = version
    if status == DialogScenario.STATUS_PRODUCTION:
        version.is_published = True
        version.published_at = timezone.now()
        version.save(update_fields=["is_published", "published_at"])
        item.status = DialogScenario.STATUS_PRODUCTION
    else:
        item.status = DialogScenario.STATUS_DRAFT
    item.save()
    return item


def published_graphs() -> list[tuple[DialogScenario, dict[str, Any]]]:
    rows: list[tuple[DialogScenario, dict[str, Any]]] = []
    qs = DialogScenario.objects.select_related("current_version").filter(
        status=DialogScenario.STATUS_PRODUCTION,
        current_version__is_published=True,
    )
    for item in qs:
        version = item.current_version
        if version is None:
            continue
        rows.append((item, version.graph or {"nodes": []}))
    return rows
