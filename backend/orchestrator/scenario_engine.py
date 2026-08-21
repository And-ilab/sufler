"""Match client turns to dialog-scenario graphs and skip phatic speech."""

from __future__ import annotations

import logging
import math
import os
import re
import threading
from datetime import timedelta
from dataclasses import dataclass
from typing import Any, Mapping

from django.utils import timezone

from hub.models import DialogScenario, DialogScenarioSession
from hub.scenario_service import published_graphs

NO_HINT_REASON = "no_hint_needed"
logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\sё+-]+", re.IGNORECASE)

_GREETING = (
    "алло",
    "ало",
    "здравствуйте",
    "здрасте",
    "добрый день",
    "добрый вечер",
    "доброе утро",
    "привет",
    "слушаю вас",
    "да слушаю",
)
_THANKS = ("спасибо", "большое спасибо", "благодарю", "все понятно", "всё понятно")
_HOLD = (
    "секунду",
    "подождите",
    "подождите пожалуйста",
    "подожди",
    "не кладите трубку",
    "минутку",
)
_FAREWELL = ("до свидания", "всего доброго", "хорошего дня", "удачи")
_ACK = ("угу", "ага", "понятно", "хорошо", "ок", "окей", "да да", "ясно")
_SHORT_ACK = ("да", "нет", "ну")
_IDENTITY_RE = re.compile(
    r"^(?:меня\s+зовут|мо[её]\s+имя|это)\s+[а-яёa-z-]+(?:\s+[а-яёa-z-]+)?$",
    re.IGNORECASE,
)
_PERSONAL_FACT_RE = re.compile(
    r"^(?:я\s+[а-яёa-z-]+|мне\s+\d{1,3}(?:\s+(?:лет|года?|год))?)$",
    re.IGNORECASE,
)
_EMPTY_INTENT = (
    "у меня вопрос",
    "можно спросить",
    "хочу спросить",
    "подскажите пожалуйста",
    "как дела",
    "что нового",
    "я вас слушаю",
    "я слушаю",
    "вы меня слышите",
    "меня слышно",
    "какая погода завтра в минске",
    "посоветуйте фильм на вечер",
    "кто выиграл вчера футбольный матч",
    "как приготовить борщ",
    "расскажите гороскоп на сегодня",
)
SESSION_TTL = timedelta(minutes=45)
SEMANTIC_THRESHOLD = 0.86
SEMANTIC_MARGIN = 0.02
SEMANTIC_THRESHOLD_EN = 0.84
SEMANTIC_MARGIN_EN = 0.035
_semantic_cache_signature: tuple[tuple[int, str], ...] | None = None
_semantic_cache_backend = ""
_semantic_cache_vectors: dict[int, list[float]] = {}
_semantic_warmup_lock = threading.Lock()
_semantic_warmup_in_progress = False


@dataclass(frozen=True)
class ScenarioProgress:
    code: str
    title: str
    path: list[str]
    node_id: str
    next_clarify: str
    hint_text: str
    node_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "path": list(self.path),
            "node_id": self.node_id,
            "next_clarify": self.next_clarify,
        }


def normalize(text: str) -> str:
    lowered = (text or "").casefold().replace("ё", "е")
    lowered = _PUNCT_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", lowered).strip()


def _tokens(text: str) -> list[str]:
    return [part for part in normalize(text).split(" ") if part]


_MATCH_STOPWORDS = {
    "а", "без", "в", "где", "для", "есть", "и", "из", "как", "когда",
    "ли", "мне", "мой", "моя", "мое", "на", "нужно", "о", "от", "по",
    "с", "у", "хочу", "что", "я",
}


_PHATIC = (*_GREETING, *_THANKS, *_HOLD, *_FAREWELL, *_ACK, *_SHORT_ACK)


def classify_turn(text: str) -> str | None:
    """Return no_hint intent id, or None if the replica may need a hint."""
    norm = normalize(text)
    if not norm:
        return "no_hint.empty"
    if _IDENTITY_RE.fullmatch(norm) or _PERSONAL_FACT_RE.fullmatch(norm):
        return "no_hint.identity"
    if norm in _EMPTY_INTENT:
        return "no_hint.smalltalk"
    leftover = f" {norm} "
    for phrase in sorted(_PHATIC, key=len, reverse=True):
        leftover = leftover.replace(f" {phrase} ", " ")
    leftover_tokens = _tokens(leftover)
    if leftover_tokens:
        return None
    if any(item in norm for item in _GREETING):
        return "no_hint.greeting"
    if any(item in norm for item in _THANKS):
        return "no_hint.thanks"
    if any(item in norm for item in _HOLD):
        return "no_hint.hold"
    if any(item in norm for item in _FAREWELL):
        return "no_hint.farewell"
    return "no_hint.ack"


def _score(
    text: str,
    keywords: list[str],
    examples: list[str],
    *,
    allow_example_overlap: bool = True,
) -> int:
    norm = normalize(text)
    if not norm:
        return 0
    score = 0
    norm_tokens = _tokens(norm)
    token_set = set(norm_tokens)
    for keyword in keywords:
        key = normalize(keyword)
        if not key:
            continue
        key_tokens = _tokens(key)
        if not key_tokens:
            continue
        if len(key_tokens) == 1:
            keyword_token = key_tokens[0]
            matched = keyword_token in token_set
            if not matched and len(keyword_token) >= 4:
                matched = any(
                    token.startswith(keyword_token)
                    or (
                        len(token) >= 4
                        and keyword_token.startswith(token)
                    )
                    for token in token_set
                )
        else:
            matched = bool(re.search(rf"(?<!\w){re.escape(key)}(?!\w)", norm))
        if matched:
            score += 3 if len(key) > 3 else 2
    best_example = 0
    for example in examples:
        example_norm = normalize(example)
        if not example_norm:
            continue
        current = 0
        if example_norm == norm:
            current = 10
        else:
            example_tokens = set(_tokens(example_norm)) - _MATCH_STOPWORDS
            overlap = example_tokens.intersection(token_set - _MATCH_STOPWORDS)
            if (
                len(norm_tokens) >= 2
                and (
                    re.search(rf"(?<!\w){re.escape(example_norm)}(?!\w)", norm)
                    or re.search(rf"(?<!\w){re.escape(norm)}(?!\w)", example_norm)
                )
            ):
                current = 10
            elif len(norm_tokens) == 1 and norm_tokens[0] in example_tokens:
                current = 2
            elif allow_example_overlap and len(overlap) >= 3:
                current = min(8, len(overlap) * 2)
            elif allow_example_overlap and len(overlap) >= 2:
                current = 3
        if current > best_example:
            best_example = current
    return score + best_example


def _nodes_by_id(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            mapping[str(node["id"])] = node
    return mapping


def _start_node(nodes: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for node in nodes.values():
        if node.get("type") == "start":
            return node
    return next(iter(nodes.values()), None)


def _progress_for(
    scenario: DialogScenario,
    node: Mapping[str, Any],
    path: list[str],
) -> ScenarioProgress:
    label = str(node.get("label") or scenario.title)
    next_path = list(path)
    if not next_path or next_path[-1] != label:
        next_path.append(label)
    hint = str(node.get("hint_text") or "").strip()
    clarify = str(node.get("clarify_text") or "").strip()
    return ScenarioProgress(
        code=scenario.code,
        title=scenario.title,
        path=next_path,
        node_id=str(node.get("id") or ""),
        next_clarify=clarify,
        hint_text=hint or clarify,
        node_type=str(node.get("type") or "answer"),
    )


def _scenario_supports_channel(scenario: DialogScenario, channel: str) -> bool:
    expected = (channel or "").strip().lower()
    actual = (scenario.channels or "both").strip().lower()
    if not expected or actual == "both":
        return True
    if expected in {"chat", "widget"}:
        expected = "online_chat"
    return actual == expected


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


def _semantic_enabled() -> bool:
    return (os.environ.get("SCENARIO_SEMANTIC_ENABLED") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _semantic_profile(
    scenario: DialogScenario,
    start: Mapping[str, Any],
) -> str:
    parts = [
        scenario.title,
        scenario.root_question,
        str(start.get("label") or ""),
        *[str(item) for item in start.get("examples") or []],
    ]
    return ". ".join(part.strip() for part in parts if part and part.strip())


def _semantic_vectors(
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> tuple[dict[int, list[float]], str]:
    global _semantic_cache_backend
    global _semantic_cache_signature
    global _semantic_cache_vectors

    signature = _semantic_signature(candidates)
    if signature == _semantic_cache_signature:
        return _semantic_cache_vectors, _semantic_cache_backend

    from core.embeddings import embed_texts_with_backend

    profiles = [
        _semantic_profile(scenario, start)
        for scenario, _graph, start in candidates
    ]
    vectors, backend = embed_texts_with_backend(profiles, is_query=False)
    _semantic_cache_signature = signature
    _semantic_cache_backend = backend
    _semantic_cache_vectors = {
        int(candidate[0].pk): vector
        for candidate, vector in zip(candidates, vectors, strict=True)
    }
    return _semantic_cache_vectors, backend


def _semantic_signature(
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> tuple[tuple[int, str], ...]:
    return tuple(
        (
            int(scenario.pk),
            (
                f"{scenario.updated_at.isoformat()}:"
                f"{scenario.current_version_id or 0}"
            ),
        )
        for scenario, _graph, _start in candidates
    )


def _warm_semantic_vectors(
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> None:
    global _semantic_warmup_in_progress

    with _semantic_warmup_lock:
        if _semantic_warmup_in_progress:
            return
        _semantic_warmup_in_progress = True

    def warm() -> None:
        global _semantic_warmup_in_progress
        try:
            _semantic_vectors(candidates)
        except Exception as exc:  # noqa: BLE001 - optional background cache
            logger.warning("scenario semantic warmup failed: %s", exc)
        finally:
            with _semantic_warmup_lock:
                _semantic_warmup_in_progress = False

    threading.Thread(
        target=warm,
        name="scenario-semantic-warmup",
        daemon=True,
    ).start()


def _match_start_semantic(
    text: str,
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> tuple[DialogScenario, dict[str, Any], dict[str, Any]] | None:
    if not _semantic_enabled():
        return None
    content_tokens = set(_tokens(text)) - _MATCH_STOPWORDS
    if len(content_tokens) < 3:
        return None
    if _semantic_cache_signature != _semantic_signature(candidates):
        _warm_semantic_vectors(candidates)
        return None
    try:
        from core.embeddings import embed_query_with_backend

        vectors = _semantic_cache_vectors
        profile_backend = _semantic_cache_backend
        query_vector, query_backend = embed_query_with_backend(text)
    except Exception as exc:  # noqa: BLE001 - semantic routing must fail open
        logger.warning("scenario semantic matching unavailable: %s", exc)
        return None
    if profile_backend not in {"http", "local"} or query_backend != profile_backend:
        return None

    ranked = sorted(
        (
            (
                _cosine_similarity(
                    query_vector,
                    vectors.get(int(scenario.pk), []),
                ),
                scenario,
                graph,
                start,
            )
            for scenario, graph, start in candidates
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked:
        return None
    best = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    has_cyrillic = bool(re.search(r"[а-яё]", text, re.IGNORECASE))
    threshold = _env_float(
        "SCENARIO_SEMANTIC_THRESHOLD",
        SEMANTIC_THRESHOLD if has_cyrillic else SEMANTIC_THRESHOLD_EN,
    )
    margin = _env_float(
        "SCENARIO_SEMANTIC_MARGIN",
        SEMANTIC_MARGIN if has_cyrillic else SEMANTIC_MARGIN_EN,
    )
    if best[0] < threshold or best[0] - runner_up < margin:
        return None
    return best[1], best[2], best[3]


def _match_start(
    text: str,
    *,
    channel: str = "",
) -> tuple[DialogScenario, dict[str, Any], dict[str, Any]] | None:
    best: tuple[int, DialogScenario, dict[str, Any], dict[str, Any]] | None = None
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ] = []
    for scenario, graph in published_graphs():
        if not _scenario_supports_channel(scenario, channel):
            continue
        nodes = _nodes_by_id(graph)
        start = _start_node(nodes)
        if start is None:
            continue
        candidates.append((scenario, graph, start))
        keywords = [scenario.title, scenario.root_question, scenario.code]
        score = _score(
            text,
            keywords,
            list(start.get("examples") or []),
            allow_example_overlap=False,
        )
        if score >= 4 and (best is None or score > best[0]):
            best = (score, scenario, graph, start)
    if best is None:
        return _match_start_semantic(text, candidates)
    return best[1], best[2], best[3]


def _match_edge(text: str, node: Mapping[str, Any], nodes: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any]] | None = None
    for edge in node.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        target_id = str(edge.get("to") or "")
        target = nodes.get(target_id)
        if target is None:
            continue
        keywords = list(edge.get("keywords") or [])
        keywords.append(str(edge.get("label") or ""))
        examples = list(target.get("examples") or [])
        score = _score(text, keywords, examples)
        # Short yes/no should still move the branch.
        norm = normalize(text)
        if norm in {"да", "ага", "угу"} and any(normalize(k) in {"да"} for k in keywords):
            score = max(score, 2)
        if norm in {"нет"} and any(normalize(k) in {"нет"} for k in keywords):
            score = max(score, 2)
        if score >= 2 and (best is None or score > best[0]):
            best = (score, target)
    return best[1] if best else None


def _save_session(session_key: str, progress: ScenarioProgress, scenario: DialogScenario) -> None:
    if not session_key:
        return
    DialogScenarioSession.objects.update_or_create(
        session_key=session_key[:160],
        defaults={
            "scenario": scenario,
            "node_id": progress.node_id,
            "path": progress.path,
        },
    )


def clear_scenario_session(session_key: str) -> None:
    key = (session_key or "").strip()[:160]
    if key:
        DialogScenarioSession.objects.filter(session_key=key).delete()


def advance_scenario(
    text: str,
    *,
    session_key: str = "",
    channel: str = "",
) -> ScenarioProgress | None:
    """Move along a published graph or start a new one from the replica."""
    key = (session_key or "").strip()[:160]
    session = None
    if key:
        session = (
            DialogScenarioSession.objects.select_related(
                "scenario",
                "scenario__current_version",
            )
            .filter(session_key=key)
            .first()
        )
        if session and session.updated_at < timezone.now() - SESSION_TTL:
            session.delete()
            session = None
    if session and session.scenario.current_version:
        scenario = session.scenario
        nodes = _nodes_by_id(session.scenario.current_version.graph or {})
        current = nodes.get(session.node_id) or _start_node(nodes)
        if current is not None:
            nxt = _match_edge(text, current, nodes)
            if nxt is not None:
                progress = _progress_for(scenario, nxt, list(session.path or []))
                if nxt.get("edges"):
                    _save_session(key, progress, scenario)
                else:
                    clear_scenario_session(key)
                return progress
            started = _match_start(text, channel=channel)
            if started and started[0].code != scenario.code:
                new_scenario, _graph, start = started
                progress = _progress_for(new_scenario, start, [])
                _save_session(key, progress, new_scenario)
                return progress
            if classify_turn(text):
                return None
            # Keep the session for a later valid branch, but never repeat the
            # current scenario hint for an unrelated replica.
            return None

    if classify_turn(text):
        return None
    started = _match_start(text, channel=channel)
    if started is None:
        return None
    scenario, _graph, start = started
    progress = _progress_for(scenario, start, [])
    _save_session(key, progress, scenario)
    return progress


def run_test_dialog(code: str, lines: list[str]) -> dict[str, Any]:
    """Sandbox walk for the admin test screen (FR-SCR-10)."""
    from hub.scenario_service import get_scenario

    scenario = get_scenario(code)
    version = scenario.current_version
    if version is None:
        return {"steps": [], "errors": ["Нет версии сценария"], "path": []}
    nodes = _nodes_by_id(version.graph or {})
    current = _start_node(nodes)
    if current is None:
        return {"steps": [], "errors": ["Нет стартового узла"], "path": []}
    path = [str(current.get("label") or scenario.title)]
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, line in enumerate(lines, start=1):
        replica = str(line or "").strip()
        if not replica:
            continue
        nxt = _match_edge(replica, current, nodes)
        if nxt is None and index == 1:
            score = _score(
                replica,
                [scenario.title, scenario.root_question],
                list(current.get("examples") or []),
            )
            if score < 2:
                errors.append(f"Шаг {index}: реплика не распознана как старт сценария")
        elif nxt is None:
            errors.append(f"Шаг {index}: нет ребра для «{replica}»")
        else:
            current = nxt
            label = str(current.get("label") or "")
            if path[-1] != label:
                path.append(label)
        steps.append(
            {
                "index": index,
                "input": replica,
                "node_id": str(current.get("id") or ""),
                "label": str(current.get("label") or ""),
                "hint_text": str(current.get("hint_text") or ""),
                "clarify_text": str(current.get("clarify_text") or ""),
                "ok": not errors or not errors[-1].startswith(f"Шаг {index}:"),
            }
        )
    return {
        "code": scenario.code,
        "title": scenario.title,
        "steps": steps,
        "errors": errors,
        "path": path,
        "ok": not errors,
    }
