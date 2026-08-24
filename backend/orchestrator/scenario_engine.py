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
SEMANTIC_THRESHOLD = 0.80
SEMANTIC_MARGIN = 0.02
SEMANTIC_THRESHOLD_EN = 0.78
SEMANTIC_MARGIN_EN = 0.03
SEMANTIC_SUGGEST_THRESHOLD = 0.60
SEMANTIC_SUGGEST_THRESHOLD_EN = 0.58
LEXICAL_AUTO_THRESHOLD = 4
LEXICAL_SUGGEST_THRESHOLD = 1
UNMATCHED_HINT = (
    "Клиент не выбрал предложенные варианты — уточните, что имеется в виду."
)
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


@dataclass(frozen=True)
class SuggestedScenario:
    code: str
    title: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True)
class ScenarioTurn:
    progress: ScenarioProgress | None = None
    suggested: SuggestedScenario | None = None
    session_active: bool = False
    unmatched: bool = False


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
_WEAK_OVERLAP = {
    "открыть", "оформить", "подскажите", "можно", "нужно", "счёт", "счет",
    "карта", "карты", "деньги", "перевод", "хотеть", "взять", "сделать",
}
_WORD_NUMBERS = {
    "ноль": 0, "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
    "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12,
    "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
    "семнадцать": 17, "восемнадцать": 18,
}
_CHILD_TOPIC = (
    "счет", "счёт", "вклад", "ребен", "ребён", "внук", "сын", "доч",
    "несовершеннолетн", "открыть", "маленьк", "карт",
)
_MINOR_PROFILE = ("несовершеннолетн", "14-лет", "внук", "ребен", "до 14")
_MINOR_QUERY = ("маленьк", "несовершеннолетн", "ребен", "внук", "подрост", "школьн")
_MINOR_PRODUCT = ("карт", "счет", "счёт", "вклад", "открыть")
_NFC_PROFILE = ("nfc", "оплата телефон", "apple pay", "apple")
_NFC_QUERY = (
    "apple pay",
    "apple",
    "pay",
    "айфон",
    "iphone",
    "nfc",
    "эпл",
    "wallet",
    "samsung pay",
    "google pay",
)
_PAYMENT_INTENT = ("оплат", "плат", "pay", "nfc", "apple", "айфон", "iphone")
_CRYPTO_MARKERS = ("крипт", "биткоин", "эфир", "ethereum", "usdt", "binance")
_CRYPTO_BLOCKERS = ("apple", "pay", "айфон", "iphone", "nfc", "эпл")
# If the scenario title is about a topic, these query stems count as the same
# theme — no need to list them in examples.
_TOPIC_CLUSTERS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("рф", "росси"),
        (
            "москв",
            "питер",
            "петербург",
            "санкт",
            "спб",
            "росси",
            "рф",
            "сбер",
        ),
    ),
    (
        ("крипт", "бирж", "биткоин"),
        (
            "эфир",
            "ethereum",
            "eth",
            "биткоин",
            "btc",
            "usdt",
            "binance",
            "bynex",
        ),
    ),
    (
        ("автокредит", "автомобил"),
        ("машин", "автокредит", "belgee", "белджи"),
    ),
)
_TRANSFER_STEMS = ("перевод", "перевест", "отправит", "перечисл", "кинуть")
_GENERIC_TRANSFER_OBJECT = (
    "деньг",
    "средств",
    "телефон",
    "номер",
    "карт",
    "счет",
    "счёт",
    "комисс",
    "просто",
    "как",
    "когда",
    "видн",
)
_RF_QUERY = (
    "рф",
    "росси",
    "москв",
    "питер",
    "петербург",
    "санкт",
    "спб",
    "сбер",
    "за рубеж",
    "за границ",
    "заграниц",
)
_OTHER_RE = re.compile(
    r"ни\s+то\s+ни|ни\s+та\s+ни|ни\s+одно|вообще\s+не\s+то|не\s+то\s+не\s+то|"
    r"ни\s+карт|другая\s+карт|другой\s+вариант|не\s+подходит|никак(?:ая|ой|ое)?|"
    r"совсем\s+друг|вообще\s+друг",
    re.IGNORECASE,
)
_DECLINE_RE = re.compile(
    r"не\s+оформл|не\s+будем\s+оформ|не\s+хочу\s+оформ|не\s+буду\s+оформ|"
    r"не\s+надо\b|не\s+нужно\b|не\s+буду\b|не\s+хотим\b|"
    r"передумал|отказыва|не\s+интересует|другой\s+вопрос|"
    r"не\s+об\s+этом|не\s+про\s+это",
    re.IGNORECASE,
)


_PHATIC = (*_GREETING, *_THANKS, *_HOLD, *_FAREWELL, *_ACK, *_SHORT_ACK)


def classify_turn(text: str) -> str | None:
    """Return no_hint intent id, or None if the replica may need a hint."""
    norm = normalize(text)
    if not norm:
        return "no_hint.empty"
    if _tokens(norm)[-1] in {"а", "без", "в", "для", "и", "или", "к", "на", "не", "о", "по", "с", "у"}:
        return "no_hint.incomplete"
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


def _with_aliases(text: str) -> str:
    norm = normalize(text)
    extras: list[str] = []
    tokens = _tokens(norm)
    has_credit = "кредит" in tokens or "автокредит" in tokens
    has_auto = any(
        token.startswith(stem)
        for token in tokens
        for stem in ("авто", "машин", "автомобил")
    )
    if "автокредит" in norm or (has_credit and has_auto):
        extras.extend(["автокредит", "кредит на автомобиль", "кредит на машину"])
    if "маленьк" in norm:
        extras.extend(["несовершеннолетний", "открыть счёт"])
    if (
        "apple pay" in norm
        or "эпл пей" in norm
        or ("apple" in tokens and "pay" in tokens)
        or "айфон" in tokens
        or "iphone" in tokens
    ):
        extras.extend(["оплата телефоном", "nfc", "apple pay"])
    if not extras:
        return text
    return f"{text} {' '.join(extras)}"


def _extract_ages(text: str) -> list[float]:
    norm = normalize(text)
    ages: list[float] = []
    for match in re.finditer(
        r"(\d+(?:[.,]\d+)?)\s+с\s+половиной(?:\s+(?:лет|года|год))?",
        norm,
    ):
        ages.append(float(match.group(1).replace(",", ".")) + 0.5)
    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{re.escape(word)}\s+с\s+половиной", norm):
            ages.append(float(value) + 0.5)
    for match in re.finditer(r"\b(\d{1,2})(?:[.,](\d))?\s+(?:лет|года|год)\b", norm):
        whole = float(match.group(1))
        if match.group(2):
            whole += float(match.group(2)) / 10
        ages.append(whole)
    for word, value in _WORD_NUMBERS.items():
        if re.search(
            rf"\b{re.escape(word)}(?:надцати)?(?:летн\w*|\s+(?:лет|года|год))\b",
            norm,
        ):
            ages.append(float(value))
    for match in re.finditer(r"\b(\d{1,2})\s+с\s+половиной\b", norm):
        ages.append(float(match.group(1)) + 0.5)
    return ages


def _has_child_topic(text: str) -> bool:
    norm = normalize(text)
    return any(marker in norm for marker in _CHILD_TOPIC)


def _contains_stem(blob: str, stems: tuple[str, ...]) -> bool:
    norm = normalize(blob)
    tokens = set(_tokens(norm))
    for stem in stems:
        if " " in stem:
            if stem in norm:
                return True
            continue
        if len(stem) <= 3:
            if stem in tokens:
                return True
            continue
        if stem in norm:
            return True
    return False


def _topic_boost(text: str, profile: str) -> int:
    """Raise the score when the replica is a specific case of the scenario theme."""
    query = normalize(text)
    prof = normalize(profile)
    if not query or not prof:
        return 0
    boost = 0
    for keys, values in _TOPIC_CLUSTERS:
        if not _contains_stem(prof, keys):
            continue
        if not _contains_stem(query, values):
            continue
        is_rf = any(key in {"рф", "росси"} for key in keys)
        if is_rf and not (
            _contains_stem(query, _TRANSFER_STEMS)
            and _contains_stem(prof, _TRANSFER_STEMS)
        ):
            continue
        is_crypto = any(key in {"крипт", "бирж", "биткоин"} for key in keys)
        if is_crypto and _contains_stem(query, _CRYPTO_BLOCKERS) and not _contains_stem(
            query, _CRYPTO_MARKERS
        ):
            continue
        boost = max(boost, 5)
    if (
        _contains_stem(prof, _MINOR_PROFILE)
        and _contains_stem(query, _MINOR_QUERY)
        and _contains_stem(query, _MINOR_PRODUCT)
    ):
        boost = max(boost, 5)
    if _contains_stem(prof, _NFC_PROFILE) and (
        _contains_stem(query, _NFC_QUERY)
        or (
            _contains_stem(query, _PAYMENT_INTENT)
            and _contains_stem(query, ("телефон", "айфон", "iphone"))
        )
    ):
        boost = max(boost, 5)
    return boost


def _is_generic_transfer_query(text: str) -> bool:
    """True for «перевод по телефону» without a destination or asset."""
    query = normalize(text)
    if not query or not _contains_stem(query, _TRANSFER_STEMS):
        return False
    leftover = [
        token
        for token in _tokens(query)
        if token not in _MATCH_STOPWORDS
        and not _contains_stem(token, _TRANSFER_STEMS)
        and not _contains_stem(token, _GENERIC_TRANSFER_OBJECT)
    ]
    return not leftover


def _scenario_conflicts_query(text: str, scenario: DialogScenario) -> bool:
    """Block an obviously wrong theme, e.g. Apple Pay vs crypto exchange."""
    query = normalize(text)
    blob = normalize(f"{scenario.title} {scenario.root_question} {scenario.code}")
    if _contains_stem(query, _CRYPTO_BLOCKERS) and not _contains_stem(
        query, _CRYPTO_MARKERS
    ):
        if _contains_stem(blob, ("крипт", "бирж")):
            return True
    if _contains_stem(query, _MINOR_QUERY) and _contains_stem(query, _MINOR_PRODUCT):
        if _contains_stem(blob, ("крипт", "автокредит")):
            return True
    # «Перевод в РФ» is a destination, not any phone transfer. Embeddings
    # otherwise pull generic «перевод по телефону» into this scenario.
    if _contains_stem(blob, ("рф", "росси")) and _contains_stem(
        query, _TRANSFER_STEMS
    ):
        if not _contains_stem(query, _RF_QUERY):
            return True
    if _is_generic_transfer_query(query) and _contains_stem(
        blob, ("крипт", "бирж", "биткоин")
    ):
        return True
    return False


def _age_boost(text: str, profile: str) -> int:
    ages = _extract_ages(text)
    if not ages or not _has_child_topic(text):
        return 0
    profile_norm = normalize(profile)
    boost = 0
    for age in ages:
        if age < 14 and re.search(
            r"до\s*14|младше\s*14|\b6\s+лет|внук|ребенк|ребёнк",
            profile_norm,
        ):
            boost = max(boost, 5)
        if 13.5 <= age <= 15 and re.search(r"14|четырнадцат", profile_norm):
            if "до 14" not in profile_norm and "младше 14" not in profile_norm:
                boost = max(boost, 4)
    return boost


def _is_other_reply(text: str) -> bool:
    return bool(_OTHER_RE.search(normalize(text)))


def _is_decline_reply(text: str) -> bool:
    return bool(_DECLINE_RE.search(normalize(text)))


def _edge_is_fallback(edge: Mapping[str, Any]) -> bool:
    return bool(edge.get("is_fallback"))


def _start_profile(scenario: DialogScenario, start: Mapping[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            scenario.title,
            scenario.root_question,
            str(start.get("label") or ""),
            " ".join(str(item) for item in start.get("examples") or []),
        ]
        if part
    )


def _score(
    text: str,
    keywords: list[str],
    examples: list[str],
    *,
    allow_example_overlap: bool = True,
) -> int:
    norm = normalize(_with_aliases(text))
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
            elif allow_example_overlap and any(
                token not in _WEAK_OVERLAP and len(token) >= 6 for token in overlap
            ):
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
    next_clarify = clarify if hint and normalize(hint) != normalize(clarify) else ""
    return ScenarioProgress(
        code=scenario.code,
        title=scenario.title,
        path=next_path,
        node_id=str(node.get("id") or ""),
        next_clarify=next_clarify,
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


def _graph_profile_text(graph: Mapping[str, Any] | None) -> str:
    parts: list[str] = []
    expansion = str((graph or {}).get("semantic_expansion") or "").strip()
    if expansion:
        parts.append(expansion)
    for node in (graph or {}).get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        for key in ("label", "hint_text", "clarify_text"):
            value = str(node.get(key) or "").strip()
            if value:
                parts.append(value)
        for example in node.get("examples") or []:
            text = str(example or "").strip()
            if text:
                parts.append(text)
        for edge in node.get("edges") or []:
            if not isinstance(edge, Mapping):
                continue
            for key in ("label", "reply"):
                value = str(edge.get(key) or "").strip()
                if value:
                    parts.append(value)
    return ". ".join(parts)[:2400]


def _semantic_profile(
    scenario: DialogScenario,
    graph: Mapping[str, Any],
    start: Mapping[str, Any],
) -> str:
    title = str(scenario.title or "").strip()
    root = str(scenario.root_question or "").strip()
    parts = [
        f"Банковский сценарий: {title}." if title else "",
        f"Клиент обычно говорит: {root}." if root else "",
        (
            f"Подходят любые формулировки про ту же тему «{title}», "
            "включая частные случаи, бренды и синонимы именно этой темы, "
            "а не соседних продуктов."
            if title
            else ""
        ),
        str(start.get("label") or ""),
        *[str(item) for item in start.get("examples") or []],
        _graph_profile_text(graph),
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
        _semantic_profile(scenario, graph, start)
        for scenario, graph, start in candidates
    ]
    vectors, backend = embed_texts_with_backend(profiles, is_query=False)
    if backend not in {"http", "local"}:
        return {}, backend
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


def _semantic_thresholds(text: str) -> tuple[float, float, float, float]:
    has_cyrillic = bool(re.search(r"[а-яё]", text, re.IGNORECASE))
    auto = _env_float(
        "SCENARIO_SEMANTIC_THRESHOLD",
        SEMANTIC_THRESHOLD if has_cyrillic else SEMANTIC_THRESHOLD_EN,
    )
    suggest = _env_float(
        "SCENARIO_SEMANTIC_SUGGEST_THRESHOLD",
        SEMANTIC_SUGGEST_THRESHOLD if has_cyrillic else SEMANTIC_SUGGEST_THRESHOLD_EN,
    )
    margin = _env_float(
        "SCENARIO_SEMANTIC_MARGIN",
        SEMANTIC_MARGIN if has_cyrillic else SEMANTIC_MARGIN_EN,
    )
    suggest_margin = _env_float(
        "SCENARIO_SEMANTIC_SUGGEST_MARGIN",
        0.01 if has_cyrillic else 0.015,
    )
    return auto, suggest, margin, suggest_margin


def _semantic_rank(
    text: str,
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> list[tuple[float, DialogScenario, dict[str, Any], dict[str, Any]]]:
    if not _semantic_enabled():
        return []
    content_tokens = set(_tokens(text)) - _MATCH_STOPWORDS
    if len(content_tokens) < 1:
        return []
    try:
        if _semantic_cache_signature != _semantic_signature(candidates):
            _warm_semantic_vectors(candidates)
            return []
        from core.embeddings import embed_query_with_backend

        vectors = _semantic_cache_vectors
        profile_backend = _semantic_cache_backend
        query_vector, query_backend = embed_query_with_backend(text)
    except Exception as exc:  # noqa: BLE001 - semantic routing must fail open
        logger.warning("scenario semantic matching unavailable: %s", exc)
        _warm_semantic_vectors(candidates)
        return []
    if profile_backend not in {"http", "local"} or query_backend != profile_backend:
        return []
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
            if not _scenario_conflicts_query(text, scenario)
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    return [item for item in ranked if item[0] > 0]


def _pick_semantic(
    ranked: list[tuple[float, DialogScenario, dict[str, Any], dict[str, Any]]],
    *,
    threshold: float,
    margin: float,
    lexical_scores: dict[str, int] | None = None,
) -> tuple[float, DialogScenario, dict[str, Any], dict[str, Any]] | None:
    if not ranked:
        return None
    best = ranked[0]
    if best[0] < threshold:
        return None
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    if best[0] - runner_up >= margin:
        return best
    scores = lexical_scores or {}
    close = [
        item
        for item in ranked
        if item[0] >= threshold and best[0] - item[0] < margin
    ]
    if not close:
        return None
    picked = max(
        close,
        key=lambda item: (
            scores.get(item[1].code, 0),
            len(str(item[1].title or "").strip()),
            item[0],
        ),
    )
    if scores.get(picked[1].code, 0) <= 0:
        return None
    return picked


def _match_start_semantic(
    text: str,
    candidates: list[
        tuple[DialogScenario, dict[str, Any], dict[str, Any]]
    ],
) -> tuple[DialogScenario, dict[str, Any], dict[str, Any]] | None:
    auto, _suggest, margin, _suggest_margin = _semantic_thresholds(text)
    lexical_scores = {
        item[1].code: item[0] for item in _lexical_start_scores(text, candidates)
    }
    picked = _pick_semantic(
        _semantic_rank(text, candidates),
        threshold=auto,
        margin=margin,
        lexical_scores=lexical_scores,
    )
    if picked is None:
        return None
    return picked[1], picked[2], picked[3]


def warm_scenario_semantics(channel: str = "") -> None:
    """Build scenario embedding cache in the background after process start."""
    candidates = _iter_start_candidates(channel)
    if candidates:
        _warm_semantic_vectors(candidates)


def _iter_start_candidates(
    channel: str = "",
) -> list[tuple[DialogScenario, dict[str, Any], dict[str, Any]]]:
    candidates: list[tuple[DialogScenario, dict[str, Any], dict[str, Any]]] = []
    for scenario, graph in published_graphs():
        if not _scenario_supports_channel(scenario, channel):
            continue
        nodes = _nodes_by_id(graph)
        start = _start_node(nodes)
        if start is None:
            continue
        candidates.append((scenario, graph, start))
    return candidates


def _lexical_start_scores(
    text: str,
    candidates: list[tuple[DialogScenario, dict[str, Any], dict[str, Any]]],
) -> list[tuple[int, DialogScenario, dict[str, Any], dict[str, Any]]]:
    scored: list[tuple[int, DialogScenario, dict[str, Any], dict[str, Any]]] = []
    for scenario, graph, start in candidates:
        if _scenario_conflicts_query(text, scenario):
            continue
        keywords = [scenario.title, scenario.root_question, scenario.code]
        score = _score(
            text,
            keywords,
            list(start.get("examples") or []),
            allow_example_overlap=True,
        )
        profile = _start_profile(scenario, start)
        score += _age_boost(text, profile)
        score += _topic_boost(text, profile)
        if score:
            scored.append((score, scenario, graph, start))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _match_start(
    text: str,
    *,
    channel: str = "",
) -> tuple[DialogScenario, dict[str, Any], dict[str, Any]] | None:
    candidates = _iter_start_candidates(channel)
    lexical = _lexical_start_scores(text, candidates)
    if lexical and lexical[0][0] >= LEXICAL_AUTO_THRESHOLD:
        return lexical[0][1], lexical[0][2], lexical[0][3]
    semantic = _match_start_semantic(text, candidates)
    if semantic is not None:
        return semantic
    return None


def _suggest_start(
    text: str,
    *,
    channel: str = "",
) -> SuggestedScenario | None:
    if _match_start(text, channel=channel) is not None:
        return None
    candidates = _iter_start_candidates(channel)
    auto, suggest, _margin, suggest_margin = _semantic_thresholds(text)
    lexical = _lexical_start_scores(text, candidates)
    lexical_scores = {item[1].code: item[0] for item in lexical}
    picked = _pick_semantic(
        _semantic_rank(text, candidates),
        threshold=suggest,
        margin=suggest_margin,
        lexical_scores=lexical_scores,
    )
    if picked is not None and picked[0] < auto:
        return SuggestedScenario(
            code=picked[1].code,
            title=picked[1].title,
            confidence=float(picked[0]),
        )
    if not lexical:
        return None
    best_score, scenario, _graph, _start = lexical[0]
    if LEXICAL_SUGGEST_THRESHOLD <= best_score < LEXICAL_AUTO_THRESHOLD:
        return SuggestedScenario(
            code=scenario.code,
            title=scenario.title,
            confidence=min(0.84, 0.55 + best_score / 20),
        )
    return None


def _edge_examples(edge: Mapping[str, Any], target: Mapping[str, Any]) -> list[str]:
    examples = [str(item) for item in target.get("examples") or []]
    reply = str(edge.get("reply") or "").strip()
    if reply:
        examples.append(reply)
    return examples


def _score_edge(text: str, edge: Mapping[str, Any], target: Mapping[str, Any]) -> int:
    keywords = list(edge.get("keywords") or [])
    keywords.append(str(edge.get("label") or ""))
    score = _score(text, keywords, _edge_examples(edge, target))
    norm = normalize(text)
    if norm in {"да", "ага", "угу"} and any(normalize(k) in {"да"} for k in keywords):
        score = max(score, 2)
    if norm in {"нет"} and any(normalize(k) in {"нет"} for k in keywords):
        score = max(score, 2)
    return score


def _match_edge(
    text: str,
    node: Mapping[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    regular: tuple[int, dict[str, Any]] | None = None
    fallback_target: dict[str, Any] | None = None
    for edge in node.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        target_id = str(edge.get("to") or "")
        target = nodes.get(target_id)
        if target is None:
            continue
        if _edge_is_fallback(edge):
            fallback_target = target
        score = _score_edge(text, edge, target)
        if _edge_is_fallback(edge):
            continue
        if score >= 2 and (regular is None or score > regular[0]):
            regular = (score, target)
    if _is_decline_reply(text):
        return fallback_target
    if regular is not None:
        return regular[1]
    if fallback_target is not None and _is_other_reply(text):
        return fallback_target
    return None


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


def _load_session(session_key: str) -> DialogScenarioSession | None:
    key = (session_key or "").strip()[:160]
    if not key:
        return None
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
        return None
    return session


def enter_scenario(
    code: str,
    *,
    session_key: str = "",
    channel: str = "",
) -> ScenarioProgress | None:
    from hub.scenario_service import get_scenario

    try:
        scenario = get_scenario(code)
    except Exception:  # noqa: BLE001 — operator click must fail open
        return None
    version = scenario.current_version
    if version is None or not version.is_published:
        return None
    if not _scenario_supports_channel(scenario, channel):
        return None
    start = _start_node(_nodes_by_id(version.graph or {}))
    if start is None:
        return None
    progress = _progress_for(scenario, start, [])
    _save_session(session_key, progress, scenario)
    return progress


def resolve_scenario_turn(
    text: str,
    *,
    session_key: str = "",
    channel: str = "",
) -> ScenarioTurn:
    """Match a scenario turn. Off-script replies leave the graph so KB can answer."""
    key = (session_key or "").strip()[:160]
    session = _load_session(key)
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
                return ScenarioTurn(progress=progress, session_active=bool(nxt.get("edges")))
            started = _match_start(text, channel=channel)
            if started and started[0].code != scenario.code:
                new_scenario, _graph, start = started
                progress = _progress_for(new_scenario, start, [])
                _save_session(key, progress, new_scenario)
                return ScenarioTurn(progress=progress, session_active=True)
            if classify_turn(text):
                return ScenarioTurn(session_active=True)
            clear_scenario_session(key)
            return ScenarioTurn(
                unmatched=True,
                suggested=SuggestedScenario(
                    code=scenario.code,
                    title=scenario.title,
                    confidence=0.72,
                ),
            )

    started = _match_start(text, channel=channel)
    if started is not None:
        scenario, _graph, start = started
        progress = _progress_for(scenario, start, [])
        _save_session(key, progress, scenario)
        return ScenarioTurn(progress=progress, session_active=True)
    suggested = _suggest_start(text, channel=channel)
    if suggested is not None:
        return ScenarioTurn(suggested=suggested)
    return ScenarioTurn()


def advance_scenario(
    text: str,
    *,
    session_key: str = "",
    channel: str = "",
) -> ScenarioProgress | None:
    """Move along a published graph or start a new one from the replica."""
    return resolve_scenario_turn(
        text,
        session_key=session_key,
        channel=channel,
    ).progress


def _test_choice(edge: Mapping[str, Any], nodes: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Return the stored client reply, with a fallback for legacy graphs."""
    label = str(edge.get("label") or "").strip()
    reply = str(edge.get("reply") or "").strip()
    if reply:
        return {"label": label, "reply": reply}

    target = nodes.get(str(edge.get("to") or ""))
    for example in list((target or {}).get("examples") or []):
        reply = str(example or "").strip()
        if reply and normalize(reply) != normalize(label):
            return {"label": label, "reply": reply}
    return {"label": label, "reply": label}


def run_test_dialog(code: str, lines: list[str]) -> dict[str, Any]:
    """Walk a selected scenario as client turns and expose operator turns."""
    from hub.scenario_service import get_scenario

    scenario = get_scenario(code)
    version = scenario.current_version
    if version is None:
        return {
            "code": scenario.code,
            "title": scenario.title,
            "steps": [],
            "errors": ["Нет версии сценария"],
            "path": [],
            "ok": False,
            "version_number": 0,
            "is_published": False,
        }
    nodes = _nodes_by_id(version.graph or {})
    current = _start_node(nodes)
    if current is None:
        return {
            "code": scenario.code,
            "title": scenario.title,
            "steps": [],
            "errors": ["Нет стартового узла"],
            "path": [],
            "ok": False,
            "version_number": version.version_number,
            "is_published": version.is_published,
        }
    path = [str(current.get("label") or scenario.title)]
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, line in enumerate(lines, start=1):
        replica = str(line or "").strip()
        if not replica:
            continue
        selected_edge = ""
        step_error = ""
        if index == 1:
            score = _score(
                replica,
                [scenario.title, scenario.root_question],
                list(current.get("examples") or []),
                allow_example_overlap=True,
            )
            score += _age_boost(replica, _start_profile(scenario, current))
            score += _topic_boost(replica, _start_profile(scenario, current))
            if score < 2:
                step_error = "Реплика не распознана как вход в выбранный сценарий"
        else:
            previous = current
            nxt = _match_edge(replica, previous, nodes)
            if nxt is None:
                choice_labels = [
                    str(edge.get("label") or "")
                    for edge in previous.get("edges") or []
                    if isinstance(edge, Mapping) and str(edge.get("label") or "")
                ]
                expected = (
                    f" Ожидалось: {', '.join(choice_labels)}."
                    if choice_labels
                    else ""
                )
                step_error = f"Ответ не подходит ни к одной ветке.{expected}"
            else:
                for edge in previous.get("edges") or []:
                    if (
                        isinstance(edge, Mapping)
                        and str(edge.get("to") or "") == str(nxt.get("id") or "")
                    ):
                        selected_edge = str(edge.get("label") or "")
                        break
                current = nxt
                label = str(current.get("label") or "")
                if path[-1] != label:
                    path.append(label)
        if step_error:
            errors.append(f"Шаг {index}: {step_error}")
        choices = [
            _test_choice(edge, nodes)
            for edge in current.get("edges") or []
            if isinstance(edge, Mapping) and str(edge.get("label") or "")
        ]
        steps.append(
            {
                "index": index,
                "input": replica,
                "node_id": str(current.get("id") or ""),
                "label": str(current.get("label") or ""),
                "hint_text": str(current.get("hint_text") or ""),
                "clarify_text": str(current.get("clarify_text") or ""),
                "selected_edge": selected_edge,
                "available_choices": choices,
                "terminal": not bool(current.get("edges")),
                "ok": not step_error,
            }
        )
    return {
        "code": scenario.code,
        "title": scenario.title,
        "steps": steps,
        "errors": errors,
        "path": path,
        "ok": not errors,
        "version_number": version.version_number,
        "is_published": version.is_published,
    }
