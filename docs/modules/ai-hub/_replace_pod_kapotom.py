#!/usr/bin/env python3
"""Replace «под капотом» with formal Russian per context."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent

INFRA = re.compile(
    r"on-prem|air-gapped|deploy|TLS|RBAC|egress|scale|cluster|CI/CD|encrypt|"
    r"audit|i18n|horizontal|PostgreSQL|K8s|BelVPN|isolated|локальн",
    re.I,
)
UI_PIPE = re.compile(
    r"\bUI\b|webhook|embed|panel|CRUD|button|thread|dropdown|canvas|upload|"
    r"preview|moderation|HITL|snippet|вкладк|панел|форм|виджет|АРМ",
    re.I,
)
ALGO = re.compile(
    r"RAG|LLM|QU|ASR|embedding|semantic|orchestration|pipeline|OCR|"
    r"lang detect|classifier|retriev|prompt|index|ETL|FeedbackEvent",
    re.I,
)


def pick_label(body: str) -> str:
    b = body.strip()
    if INFRA.search(b) and not ALGO.search(b[:40]):
        return "Обеспечивается за счёт"
    if UI_PIPE.search(b) and ALGO.search(b):
        return "Механизм реализации"
    if UI_PIPE.search(b):
        return "Реализовано посредством"
    if ALGO.search(b):
        return "Механизм реализации"
    if INFRA.search(b):
        return "Обеспечивается за счёт"
    return "Механизм реализации"


def replace_block_label(match: re.Match[str]) -> str:
    body = match.group(1)
    return f"**{pick_label(body)}:** {body}"


def transform_text(text: str) -> str:
    # prose (exact)
    text = text.replace(
        "(вход → под капотом → выход → приёмка)",
        "(вход → механизм реализации → выход → приёмка)",
    )
    text = text.replace(
        "Под капотом чата и телефонии — **один** контур Hub; различие — только UI (АРМ vs панель суфлёра).",
        "Обеспечивается за счёт **единого** контура Hub для чата и телефонии; различие — только UI (АРМ vs панель суфлёра).",
    )
    # table / template headers
    text = text.replace("| **Под капотом** |", "| **Механизм реализации** |")
    text = text.replace("**Вход** → **Под капотом** →", "**Вход** → **Механизм реализации** →")
    text = text.replace("**Вход:**", "**Вход:**")  # noop anchor

    # implementation blocks **Под капотом:** … until **Выход:**
    text = re.sub(
        r"\*\*Под капотом:\*\* ([^*]+?)(?=\*\*Выход)",
        replace_block_label,
        text,
    )
    # any remaining (fallback without following Выход)
    text = re.sub(
        r"\*\*Под капотом:\*\* (.+?)(?=\*\*Приёмка|\*\*Выход|$)",
        replace_block_label,
        text,
    )
    text = re.sub(r"\*\*Под капотом\*\*", "**Механизм реализации**", text)
    text = re.sub(r"(?<!\w)под капотом(?!\w)", "механизм реализации", text, flags=re.I)
    text = re.sub(r"(?<!\w)Под капотом(?!\w)", "Механизм реализации", text)
    return text


def patch_py_sources() -> None:
    for path in [
        ROOT / "fr_realizatsiya.py",
        ROOT / "_add_realizatsiya_column.py",
        ROOT / "_apply_v13.py",
        ROOT / "_gen_v13_artifacts.py",
    ]:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        if "под капотом" not in src.lower() and "Под капотом" not in src:
            continue
        new = transform_text(src)
        # generator: use pick_label in _wrap instead of fixed string
        if path.name == "fr_realizatsiya.py":
            new = new.replace(
                'parts.append(f"**Под капотом:** {under}")',
                'parts.append(f"**{pick_label(under)}:** {under}")',
            )
            if "def pick_label" not in new:
                insert_at = new.find("def _s(text: str)")
                pick_fn = '''
def pick_label(body: str) -> str:
    b = body.strip()
    infra = re.compile(
        r"on-prem|air-gapped|deploy|TLS|RBAC|egress|scale|cluster|CI/CD|encrypt|"
        r"audit|i18n|horizontal|PostgreSQL|K8s|isolated|локальн", re.I
    )
    ui = re.compile(
        r"\\\\bUI\\\\b|webhook|embed|panel|CRUD|button|thread|dropdown|canvas|"
        r"upload|preview|moderation|HITL|snippet|вкладк|панел|форм|виджет|АРМ", re.I
    )
    algo = re.compile(
        r"RAG|LLM|QU|ASR|embedding|semantic|orchestration|pipeline|OCR|"
        r"lang detect|classifier|retriev|prompt|index|ETL|FeedbackEvent", re.I
    )
    if infra.search(b) and not algo.search(b[:40]):
        return "Обеспечивается за счёт"
    if ui.search(b) and algo.search(b):
        return "Механизм реализации"
    if ui.search(b):
        return "Реализовано посредством"
    if algo.search(b):
        return "Механизм реализации"
    if infra.search(b):
        return "Обеспечивается за счёт"
    return "Механизм реализации"


'''
                new = new[:insert_at] + pick_fn + new[insert_at:]
        path.write_text(new, encoding="utf-8")
        print("Patched", path.name)


def main() -> None:
    tz = ROOT / "tz-unified-v1.3.md"
    text = tz.read_text(encoding="utf-8")
    out = transform_text(text)
    tz.write_text(out, encoding="utf-8")
    left = len(re.findall(r"под капотом|Под капотом", out, re.I))
    print(f"Updated {tz}; remaining matches: {left}")
    patch_py_sources()


if __name__ == "__main__":
    main()
