#!/usr/bin/env python3
"""Prepare tz-unified-v1.2.md for customer Word export.

Customer version removes internal workflow material not needed by the customer.
Source ``tz-unified-v1.2.md`` is unchanged; this script writes a filtered copy for
Word export (``export-unified-to-word.ps1``, default mode).

Meeting protocol and zero-tolerance «протокол» in customer text
    Entire sections II.0 / III.0 / IV.0 / VI.0.2 / VI.1.6 / VI.2.6 / C.3;
    TOC entries for those sections; 0.2 table row and 0.3 assignment block;
    Appendix D protocol rows; links to meeting-protocols/; cross-refs §II.0 /
    §III.0 / §IV.0; inline «протокол №2», «протокол встречи», «ПРОТОКОЛ
    ВСТРЕЧИ», «поручения протокола», «Источник: … ПРОТОКОЛ …».
    Remaining substrings «протокол» (incl. «Протоколирование», «протокол
    INT-T», integration-doc link text) are rephrased to customer-facing terms
    (журналирование, интерфейс, документ интеграции, спецификации) so that a
    case-insensitive grep finds zero hits.

Internal document links (stripped — bold text only, no repo paths)
    ``docs/sources/``, ``../../sources/`` — customer materials catalog
    ``docs/remarks/``, ``../../remarks/``, plan-dorabotok — remark workflows
    ``tz-ai-hub-contour.md`` — v1.1 predecessor archive
    ``meeting-protocols/``, BANK.ldif, active-directory exports
    ``canvases/``, ``../../ui/``, ``_comment_map`` — internal UI/mockup assets

Sections removed entirely from customer export
    Header «Предшественник», «Справочные документы», «Планы доработок»
    Subsection «Перенос FR/UC из v1.1 (замена имён)» in I.1
    Subsection VI.0.1 (``docs/sources/`` catalog)
    Appendix C (internal sources catalog) and Appendix D (remarks index)
    Manual ``## Содержание`` block from source (replaced after filtering by a
    generated ``## Содержание`` with heading links only; Word export skips
    pandoc ``--toc`` because the Word TOC field renders empty until updated)

Preserved for customer (text only, no file paths)
    **[Прил.1]** / **[Прил.2]** contract references
    Integration ``tz-*.md`` deliverable names (bold, no hyperlink)
    In-document anchor links (#section)

Workflow status columns (internal drafting markers)
    I.1 «Легенда статусов» and «Статус» columns in FR/UC tables are stripped.

Blocks wrapped in source MD with HTML comments are also removed::

    <!-- customer-hide-start -->
    ...
    <!-- customer-hide-end -->

Internal export (-Internal in export-unified-to-word.ps1) bypasses this script
and uses the source file unchanged.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Pandoc input format: GFM-style header IDs match in-doc [#anchor] links in tz-unified-v1.2.md.
PANDOC_MARKDOWN_FROM = "markdown+gfm_auto_identifiers+header_attributes"

# Known link targets that differ from Pandoc GFM auto-IDs (legacy slugs in cross-refs).
_ANCHOR_REMAP: dict[str, str] = {
    "i10-информационная-безопасность": "i9-информационная-безопасность",
    "i41-роли-прил1-§24": "i41-роли-прил1-24",
    "i91-требования-информационной-безопасности-§8-тт": "i91-требования-информационной-безопасности-8-тт",
    "ii35-редактор-диалоговых-сценариев": "ii351-редактор-диалоговых-сценариев",
    "ii352-конфигурация-llm-контакт-центра": "ii352-конфигурация-llm-контакт-центра-sufler_cc",
    "ii5-модуль-онлайн-чат-§2223-§44": "ii5-модуль-онлайн-чат-2224-44",
    "ii57-открытые-вопросы": "ii57-функциональные-требования",
    "ii71-suf-t-суфлёр": "ii71-suf-t-интерфейсы-суфлёра-43-46",
    "iii111-параметры-модели-llm-§33": "iii111-параметры-модели-llm-33",
    "iii65-политика-sql--код-§5139": "iii65-политика-sql--код-5139",
    "iii7-интеграции": "iii7-интеграции-и-api",
    "iv62-отчётность-§62": "iv62-отчётность-62",
    "v2-конфигурация-моделей-и-rag-33-35": "v2-конфигурация-моделей-и-rag-3335",
    "v2-конфигурация-моделей-и-rag-§33–35": "v2-конфигурация-моделей-и-rag-3335",
    "vii1-состав-и-этапы-работ": "vii1-состав-и-содержание-работ",
    "vii3-подготовка-объекта-вводу": "vii3-подготовка-объекта-к-вводу",
    "часть-ii-модуль-контакт-центра-§222-§4": "часть-ii-модуль-контакт-центра-222-4",
    "часть-iii-модуль-ии-ассистент-§223-§5": "часть-iii-модуль-ии-ассистент-223-5",
    "часть-iv-модуль-распознавания-документов-§224-§6": "часть-iv-модуль-распознавания-документов-224-6",
    "часть-v-модуль-llm-§221-§3": "часть-v-модуль-llm-221-3",
    "часть-v-модуль-llm-§2221-§3": "часть-v-модуль-llm-2221-3",
}

# Entire subsections devoted to meeting protocol #2 (heading → next sibling heading).
_PROTOCOL_SECTIONS: tuple[tuple[str, str], ...] = (
    (r"^## II\.0\.", r"^## II\.1\."),
    (r"^## III\.0\.", r"^## III\.1\."),
    (r"^## IV\.0\.", r"^## IV\.1\."),
    (r"^### VI\.0\.2\.", r"^### VI\.0\.\d+\.|^## VI\.1\."),
    (r"^### VI\.1\.6\.", r"^### VI\.1\.7|^## VI\.2\."),
    (r"^### VI\.2\.6\.", r"^### VI\.2\.7|^## VI\.3\."),
    (r"^## C\.3\.", r"^## C\.4\."),
)

# Internal-only subsections omitted from customer deliverable (heading → next sibling).
_CUSTOMER_ONLY_SECTIONS: tuple[tuple[str, str], ...] = (
    (r"^### Перенос FR/UC из v1\.1 \(замена имён\)", r"^## "),
    (r"^### VI\.0\.1\.", r"^### VI\.0\.\d+\.|^## VI\.1\."),
)

# Entire appendices omitted from customer deliverable.
_INTERNAL_APPENDICES: tuple[tuple[str, str], ...] = (
    (r"^# Приложение C\. Источники разработки", r"^# Приложение D\."),
    (r"^# Приложение D\. Индекс замечаний v1\.2", r"\Z"),
)

# Path fragments identifying internal working documents (repo-local).
_INTERNAL_PATH_MARKERS: tuple[str, ...] = (
    "docs/sources/",
    "../../sources/",
    "../sources/",
    "docs/remarks/",
    "../../remarks/",
    "../remarks/",
    "plan-dorabotok",
    "tz-ai-hub-contour.md",
    "meeting-protocols/",
    "active-directory/",
    "bank.ldif",
    "canvases/",
    "../../../canvases/",
    "../../ui/",
    "../ui/",
    "docs/ui/",
    "_comment_map",
    "_remarks_grouped",
    "agent-transcripts",
    "agent_transcripts",
)

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

_INLINE_BACKTICK_PATH = re.compile(
    r"`(?:"
    r"(?:\.\./)+(?:sources|remarks|ui|canvases)/[^`]+|"
    r"docs/(?:sources|remarks|ui)/[^`]+|"
    r"canvases/[^`]+|"
    r"_comment_map|_remarks_grouped"
    r")`",
    re.IGNORECASE,
)

_LITERAL_INTERNAL_PATH = re.compile(
    r"(?:\.\./)+sources/[^\s\)\],;|`]+|"
    r"docs/sources/?[^\s\)\],;|`]*|"
    r"(?:\.\./)+remarks/[^\s\)\],;|`]+|"
    r"docs/remarks/?[^\s\)\],;|`]*|"
    r"canvases/[^\s\)\],;|`]+|"
    r"plan-dorabotok(?:-v1\.2)?(?:\.md)?(?:/[^\s\)\],;|`]*)?|"
    r"tz-ai-hub-contour\.md|"
    r"meeting-protocols/[^\s\)\],;|`]*|"
    r"BANK\.ldif|"
    r"_comment_map|_remarks_grouped",
    re.IGNORECASE,
)

_HEADER_PREDECESSOR = re.compile(
    r"^\*\*Предшественник:\*\*[^\n]*\n\n?",
    re.MULTILINE,
)
_HEADER_REFERENCE_DOCS = re.compile(
    r"^\*\*Справочные документы \(не дублировать в v1\.2\):\*\*\n\n"
    r"(?:- [^\n]+\n)+",
    re.MULTILINE,
)
_HEADER_PLAN_DORABOTOK = re.compile(
    r"^\*\*Планы доработок по замечаниям заказчика:\*\*\n\n"
    r"(?:- [^\n]+\n)+",
    re.MULTILINE,
)

_TOC_APPENDIX_CD = re.compile(
    r"^- \[(?:Приложение C\.|Приложение D\.)[^\n]+\n",
    re.MULTILINE,
)

_I1_ASIS_PRIORITY = re.compile(
    r"^2\. \*\*As-Is\*\* — описание функциональности[^\n]*\n",
    re.MULTILINE,
)
_I1_PLAN_PRIORITY = re.compile(
    r"^3\. \*\*plan-dorabotok-v1\.2\*\* —[^\n]*\n",
    re.MULTILINE,
)
_I1_GOST_PRIORITY = re.compile(
    r"^4\. \*\*ГОСТ 34\.602-2020\*\*",
    re.MULTILINE,
)

_SOURCE_TABLE_PROTOCOL_ROW = re.compile(
    r"^\| Протокол встречи №2 \|[^\n]*\n",
    re.IGNORECASE | re.MULTILINE,
)
_GOST_APPENDIX_C_ROW = re.compile(
    r"^\| 9\. Источники разработки \| Приложение C \|\n",
    re.MULTILINE,
)
_STATUS_APPENDIX_D_ROW = re.compile(
    r"^\| \*\*закрыто текстом\*\* \| Замечание заказчика[^\n]*Приложение D[^\n]*\n",
    re.MULTILINE,
)

_CUSTOMER_HIDE_BLOCK = re.compile(
    r"<!--\s*customer-hide-start\s*-->.*?<!--\s*customer-hide-end\s*-->",
    re.DOTALL | re.IGNORECASE,
)

# Table/list rows whose primary topic is the meeting protocol.
_PROTOCOL_TABLE_ROW = re.compile(
    r"^\|[^\n]*(?:"
    r"протокол\s*(?:встречи|№\s*2|#2)"
    r"|протокол\s*№2"
    r"|протоколы\s+совещаний"
    r"|meeting-protocols/"
    r"|ПРОТОКОЛ\s+ВСТРЕЧИ"
    r"|поручения\s+протокола"
    r"|Пункт\s+ТТ\s*/\s*протокола"
    r"|Пункт\s+протокола"
    r")[^\n]*\|\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Standalone paragraphs / bullets about meeting protocol assignments.
_PROTOCOL_PARAGRAPH = re.compile(
    r"^\*\*Поручения протокола[^\n]*\*\*[^\n]*\n",
    re.IGNORECASE | re.MULTILINE,
)
_03_PROTOCOL_ASSIGNMENTS = re.compile(
    r"^\*\*Поручения протокола №2[^\n]*:\*\*[^\n]*\n\n?",
    re.MULTILINE | re.IGNORECASE,
)
_SOURCE_PROTOCOL_LINE = re.compile(
    r"^Источник:\s*[^\n]*(?:ПРОТОКОЛ|meeting-protocols/)[^\n]*\n\n?",
    re.MULTILINE | re.IGNORECASE,
)
_TRACING_PROTOCOL_BLOCK = re.compile(
    r"^\*\*Трассировка поручений протокола[^\n]*\n\n(?:\|[^\n]+\|\n)+",
    re.MULTILINE | re.IGNORECASE,
)
_PROTOCOL_BULLET = re.compile(
    r"^-\s*\[ПРОТОКОЛ\s+ВСТРЕЧИ[^\n]*\n",
    re.IGNORECASE | re.MULTILINE,
)
_PROTOCOL_ASSIGNMENT_LINE = re.compile(
    r"^\*\*Ближайшие поручения \(протокол[^\n]*\n",
    re.IGNORECASE | re.MULTILINE,
)

# TOC entries for removed II.0 / III.0 / IV.0 sections.
_TOC_PROTOCOL_LINE = re.compile(
    r"^- \[(?:II|III|IV)\.0[^\]]*\]\([^\)]+\)\s*\n",
    re.IGNORECASE | re.MULTILINE,
)
_ORPHAN_TOC_BULLET = re.compile(r"^-\s*\n", re.MULTILINE)

# Cross-links to removed protocol sections.
_PROTOCOL_SECTION_LINK = re.compile(
    r"\[(?:II|III|IV)\.0[^\]]*\]\(#[^\)]+\)",
    re.IGNORECASE,
)

# Links into meeting-protocols/ source folder.
_MEETING_PROTOCOLS_LINK = re.compile(
    r"\[[^\]]*\]\([^\)]*meeting-protocols/[^\)]*\)",
    re.IGNORECASE,
)

# Inline meeting-protocol phrases (order: longer patterns first).
_INLINE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\s*\(источники:\s*[^)]*meeting-protocols/[^)]*\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\s*\(источник:\s*[^)]*meeting-protocols/[^)]*\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r",\s*сводка\s*—\s*\[II\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r";\s*сводка\s*—\s*\[II\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\s*\(\[II\.0\]\([^\)]+\)\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r",\s*\[II\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\s*\[II\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"ВКС\s*§?\s*\[?(?:III|IV)\.0\]?[^\s;,\)]*",
            re.IGNORECASE,
        ),
        "ВКС",
    ),
    (
        re.compile(
            r"§\s*\[?(?:III|IV)\.0\]?[^\s;,\)]*",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"на\s+ВКС\s+§[^\s;,\)]*",
            re.IGNORECASE,
        ),
        "на ВКС",
    ),
    (
        re.compile(
            r"после\s+ВКС\s+§[^\s;,\.]+\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"Конкретный перечень `doc_type` для пилота\s*—\s*на\s+ВКС[^\n]*\.",
            re.IGNORECASE,
        ),
        "Конкретный перечень `doc_type` для пилота — на ВКС.",
    ),
    (
        re.compile(
            r"\*\*Протокол\s+№2\s+п\.\s*[\d.]+\*\*:?\s*[^;\n|]+;?\s*",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\(протокол\s+№2[^)]*\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"по\s+п\.\s*[\d.]+\s+протокола\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"на\s+дату\s+протокола\s+№2\b",
            re.IGNORECASE,
        ),
        "на дату черновика v1.2",
    ),
    (
        re.compile(
            r"протокол\s+№2\s+п\.[\d.]+\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"Протокол\s+№2\s+п\.[\d.]+\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"протокол\s+№2\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"Протокол\s+№2\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"протокол\s+встречи\s*#?\s*2\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"ПРОТОКОЛ\s+ВСТРЕЧИ\s*#?\s*2\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"поручени[яе]\s+протокола\b",
            re.IGNORECASE,
        ),
        "поручения",
    ),
    (
        re.compile(
            r"зависимости\s+приёмки\s+Part\s+II\s*\(протокол[^\)]*\):?",
            re.IGNORECASE,
        ),
        "Зависимости приёмки Part II:",
    ),
    (
        re.compile(
            r"Срок\s*\(протокол\)",
            re.IGNORECASE,
        ),
        "Срок",
    ),
    (
        re.compile(
            r"после\s+выполнения\s+поручений\s+протокола\s+№2\s*\([^)]*\)",
            re.IGNORECASE,
        ),
        "после подготовки стендов",
    ),
    (
        re.compile(
            r"уточнение\s+протокола\b",
            re.IGNORECASE,
        ),
        "уточнение",
    ),
    (
        re.compile(
            r"готово;\s*ВКС\s+§[^\|]+\|",
            re.IGNORECASE,
        ),
        "готово |",
    ),
    (
        re.compile(
            r"\*\*II\.0\*\*|\*\*IV\.0\*\*",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\b(?:II|III|IV)\.0\b(?=\s*,|\s*;|\s*\||\s*\))",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"в\s+протоколах\b",
            re.IGNORECASE,
        ),
        "в исходных материалах",
    ),
    (
        re.compile(
            r"зафиксированы\s+протоколы\s+решений",
            re.IGNORECASE,
        ),
        "зафиксированы решения",
    ),
    (
        re.compile(
            r";\s*поручения\s+протоколов\s+встреч;\s*",
            re.IGNORECASE,
        ),
        "; ",
    ),
    (
        re.compile(
            r",\s*\[VI\.0\.2\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"вопросники,\s*протоколы,\s*",
            re.IGNORECASE,
        ),
        "вопросники, ",
    ),
    (
        re.compile(
            r"протоколы,\s*AD\b",
            re.IGNORECASE,
        ),
        "AD",
    ),
    (
        re.compile(
            r"0\.3,\s*I\.2,\s*\*\*II\.0\*\*,\s*\*\*IV\.0\*\*,",
            re.IGNORECASE,
        ),
        "0.3, I.2,",
    ),
    (
        re.compile(
            r"→\s*\[II\.0\]\([^\)]+\);\s*ВКС\s+OCR\s*→\s*\[IV\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"→\s*\[II\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r",\s*\[IV\.0\]\([^\)]+\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\[IV\.0\]\([^\)]+\),\s*",
            re.IGNORECASE,
        ),
        "",
    ),
)

# Rephrase remaining «протокол» substrings for customer-facing text (order: longer first).
_NEUTRALIZE_PROTO_WORD: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Протоколирование", re.IGNORECASE), "Журналирование"),
    (re.compile(r"протоколированием", re.IGNORECASE), "журналированием"),
    (re.compile(r"протоколирования", re.IGNORECASE), "журналирования"),
    (re.compile(r"протоколирование", re.IGNORECASE), "журналирование"),
    (re.compile(r"система протоколирования", re.IGNORECASE), "система журналирования"),
    (re.compile(r"Целевой протокол INT-T", re.IGNORECASE), "Целевой интерфейс INT-T"),
    (re.compile(r"целевой протокол INT-T", re.IGNORECASE), "целевой интерфейс INT-T"),
    (re.compile(r"Согласованный протокол и схема", re.IGNORECASE), "Согласованный интерфейс и схема"),
    (re.compile(r"согласованного протокола", re.IGNORECASE), "согласованного интерфейса"),
    (re.compile(r"протокол событий", re.IGNORECASE), "интерфейс событий"),
    (re.compile(r"протокол интеграции СУЗ", re.IGNORECASE), "документ интеграции СУЗ"),
    (re.compile(r"протокол интеграции Oktell", re.IGNORECASE), "документ интеграции Oktell"),
    (re.compile(r"\(протокол §8\)", re.IGNORECASE), "(документ интеграции §8)"),
    (re.compile(r"протокол прогона", re.IGNORECASE), "отчёт прогона"),
    (re.compile(r"API, протоколы", re.IGNORECASE), "API, спецификации"),
    (re.compile(r"вопросники, протоколы,", re.IGNORECASE), "вопросники,"),
    (re.compile(r"протоколы, AD", re.IGNORECASE), "AD"),
    (re.compile(r"протоколы решений", re.IGNORECASE), "решения"),
    (re.compile(r"протоколы совещаний", re.IGNORECASE), "материалы совещаний"),
    (re.compile(r"в протоколах", re.IGNORECASE), "в исходных материалах"),
    (re.compile(r"Реестр вопросов \(протокол №2 и воркшопы\)", re.IGNORECASE), "Реестр вопросов (воркшопы)"),
)

# I.1 workflow-status legend (internal drafting markers).
_STATUS_LEGEND_SECTION = re.compile(
    r"(?ms)^### Легенда статусов в таблицах\n\n.*?(?=^### )",
)

# Source hand-written «Содержание» (removed; replaced by _generate_toc_section).
_MANUAL_TOC_SECTION = re.compile(
    r"(?ms)^## Содержание\n\n.*?(?=^# Часть 0\.)",
)

# H3 headings included in generated TOC (numbered subsections only, not generic ### titles).
_TOC_H3_NUMBER = re.compile(
    r"^(?:[0-9]+\.[0-9]+\.[0-9]+|[IVX]+\.[0-9]+\.[0-9]+)",
    re.IGNORECASE,
)
_TOC_H3_EXCLUDE_PREFIXES: tuple[str, ...] = (
    "Правило наименования",
    "Легенда маркеров",
    "Легенда статусов",
    "Таблица трассировки",
    "Перенос FR/UC",
)

_FIRST_PART_HEADING = re.compile(r"^# Часть ", re.MULTILINE)

# Cleanup after removals (horizontal whitespace only — do not eat newlines before table pipes).
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,;:\)])")
_DOUBLE_SPACE = re.compile(r"[^\S\n]{2,}")
_ORPHAN_SEMICOLON = re.compile(r"[ \t]*;[ \t]*;")
_TRAILING_SEMICOLON_SPACE = re.compile(r"[ \t]*;[ \t]*(\||$)", re.MULTILINE)


def _remove_sections_between_headings(
    text: str, sections: tuple[tuple[str, str], ...]
) -> str:
    for start_pat, end_pat in sections:
        pattern = re.compile(rf"(?ms)^{start_pat}.*?(?=^{end_pat})")
        text = pattern.sub("", text)
    return text


def _remove_protocol_sections(text: str) -> str:
    return _remove_sections_between_headings(text, _PROTOCOL_SECTIONS)


def _remove_customer_only_sections(text: str) -> str:
    return _remove_sections_between_headings(text, _CUSTOMER_ONLY_SECTIONS)


def _remove_internal_appendices(text: str) -> str:
    return _remove_sections_between_headings(text, _INTERNAL_APPENDICES)


def _contract_link_text(link_text: str, url: str) -> str | None:
    """Map prilozhenie-1 paths to **[Прил.1]** / **[Прил.2]** for customer text."""
    normalized = url.lower().replace("\\", "/")
    if "prilozhenie-1" not in normalized and "technical-requirements/prilozhenie" not in normalized:
        if "app2-scenarios" in normalized or "manifest.yaml" in normalized:
            return "**Прил.2**"
        return None
    if "§" in link_text:
        return f"**Прил.1 {link_text.split('§', 1)[1].strip()}**"
    if "прил.2" in link_text.lower() or "прил. 2" in link_text.lower():
        return "**Прил.2**"
    return "**Прил.1**"


def _is_internal_doc_url(url: str) -> bool:
    if url.startswith("#"):
        return False
    normalized = url.strip().lower().replace("\\", "/")
    if normalized.startswith(("http://", "https://", "mailto:")):
        return False
    return any(marker in normalized for marker in _INTERNAL_PATH_MARKERS)


def _customer_label_for_internal_url(link_text: str, url: str) -> str:
    """Readable customer label for repo-local source paths (no file URLs)."""
    normalized = url.lower().replace("\\", "/")
    clean = link_text.strip("`").strip()

    if "bank.ldif" in normalized:
        return "тестовый экспорт AD"
    if "plan-dorabotok" in normalized or "plan-dorabotok" in clean.lower():
        version = re.search(r"v1\.\d+", clean, re.IGNORECASE)
        return f"замечания заказчика {version.group()}" if version else "замечания заказчика"
    if "oktell" in normalized or "oktell" in clean.lower():
        return "исходные материалы Oktell"
    if "active-directory" in normalized or "структура_ad" in clean.lower():
        return "Структура AD"
    if "/suz/" in normalized or normalized.endswith("/suz"):
        return "исходные материалы СУЗ"
    if "meeting-protocols" in normalized:
        return "исходные материалы совещаний"
    if "docs/sources" in clean.lower() or "/sources/" in normalized:
        return "исходные материалы заказчика"
    if clean and not re.search(r"^(?:\.\./)+|docs/", clean, re.IGNORECASE):
        return clean
    return "исходные материалы заказчика"


def _normalize_bold_wrapped_source_links(text: str) -> str:
    """Resolve ``**[`docs/sources/...`](../../sources/...)`` before generic link pass."""

    def _replace(match: re.Match[str]) -> str:
        prefix = match.group(1) or ""
        suffix = match.group(4) or ""
        label = _customer_label_for_internal_url(match.group(2), match.group(3))
        return f"**{prefix}{label}{suffix}**"

    pattern = re.compile(
        r"\*\*([^*\[]*)"
        r"\[`([^`]+)`\]\(([^)]+)\)"
        r"([^*]*)\*\*",
        re.IGNORECASE,
    )
    return pattern.sub(_replace, text)


def _cleanup_markdown_artifacts(text: str) -> str:
    text = re.sub(r"\*\*(?:\s|\*)*\*\*", "", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r":\s*:\s*", ": ", text)
    text = re.sub(r"\*\*Уже в\s*:\*\*", "**Уже в исходных материалах Oktell:**", text)
    text = re.sub(r"Исходные материалы \*\*исходные материалы Oktell\*\*", "**Исходные материалы Oktell**", text)
    text = re.sub(r"``+", "", text)
    text = re.sub(r"замечания\s+v1\.", "замечания заказчика v1.", text, flags=re.IGNORECASE)
    text = re.sub(r"  +", " ", text)
    return text


def _strip_internal_markdown_links(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        link_text = match.group(1)
        url = match.group(2)
        if url.startswith("#"):
            if re.search(r"протокол", url, re.IGNORECASE):
                return f"**{link_text}**"
            return match.group(0)
        contract = _contract_link_text(link_text, url)
        if contract is not None:
            return contract
        if re.search(r"протокол", url, re.IGNORECASE) or re.search(
            r"протокол", link_text, re.IGNORECASE
        ):
            clean = re.sub(
                r"протокол",
                lambda m: "Документ" if m.group().istitle() else "документ",
                link_text,
                flags=re.IGNORECASE,
            )
            return f"**{clean}**"
        if "tz-ai-hub-contour.md" in url.lower():
            section = ""
            if "§" in link_text:
                section = f" ({link_text.split('§', 1)[1].strip()})"
            return f"**версии v1.1{section}**"
        if _is_internal_doc_url(url):
            return f"**{_customer_label_for_internal_url(link_text, url)}**"
        if "/" in url or url.endswith(".md") or url.endswith(".yaml"):
            return f"**{link_text}**"
        return match.group(0)

    return _MARKDOWN_LINK.sub(_replace, text)


def _strip_inline_internal_paths(text: str) -> str:
    text = re.sub(
        r"\*\*tz-ai-hub-contour\.md[^*]*\*\*",
        "**версии v1.1**",
        text,
        flags=re.IGNORECASE,
    )
    text = _INLINE_BACKTICK_PATH.sub("", text)
    text = _LITERAL_INTERNAL_PATH.sub("", text)
    text = re.sub(r"\(\s*источники:\s*[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\(\s*источник:\s*[^)]*(?:meeting-protocols/|sources/)[^)]*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"из\s+[`'\"]?docs/sources/?[`'\"]?\s*",
        "из исходных материалов заказчика ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"[`'\"]docs/sources/[^`'\"]*[`'\"]",
        "исходные материалы заказчика",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\*\*plan-dorabotok[^*]*\*\*",
        "замечания заказчика",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\[plan-dorabotok[^\]]*\]",
        "замечания заказчика",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _remove_internal_header_blocks(text: str) -> str:
    text = _HEADER_PREDECESSOR.sub("", text)
    text = _HEADER_REFERENCE_DOCS.sub("", text)
    text = _HEADER_PLAN_DORABOTOK.sub("", text)
    return text


def _simplify_i1_priority_list(text: str) -> str:
    text = _I1_ASIS_PRIORITY.sub(
        "2. **As-Is** — описание функциональности, действующей в настоящее время "
        "(исходные материалы заказчика); фиксирует ограничения интеграции.\n",
        text,
    )
    text = _I1_PLAN_PRIORITY.sub("", text)
    text = _I1_GOST_PRIORITY.sub("3. **ГОСТ 34.602-2020**", text)
    return text


def _remove_internal_catalog_rows(text: str) -> str:
    text = _SOURCE_TABLE_PROTOCOL_ROW.sub("", text)
    text = _GOST_APPENDIX_C_ROW.sub("", text)
    text = _STATUS_APPENDIX_D_ROW.sub(
        "| **закрыто текстом** | Замечание заказчика учтено в тексте настоящего ТЗ |\n",
        text,
    )
    return text


def _strip_internal_document_links(text: str) -> str:
    text = _strip_internal_markdown_links(text)
    text = _strip_inline_internal_paths(text)
    return text


def _remove_v2_context_block(text: str) -> str:
    """Remove V.2 bullet list citing ПРОТОКОЛ ВСТРЕЧИ #2."""
    pattern = re.compile(
        r"(?ms)^\*\*Контекст внедрения \(источники встречи\):\*\*\n\n"
        r"(?:- \[[^\]]+\]\([^\)]*meeting-protocols/[^\)]*\)[^\n]*\n)+"
        r"\n(?=> )",
    )
    return pattern.sub("", text)


def _remove_v2_dependencies_table(text: str) -> str:
    """Remove V.2.2 table rows sourced from Протокол №2."""
    pattern = re.compile(
        r"(?ms)^\| Спецификация полей/формата/триггеров СУЗ \| Протокол №2[^\n]*\n"
        r"\| Проработка API/варианта выгрузки СУЗ заказчиком \| Протокол №2[^\n]*\n"
        r"\| Тестовый контур Bitrix \| Протокол №2[^\n]*\n",
    )
    return pattern.sub("", text)


def _remove_part_ii_dependencies_block(text: str) -> str:
    pattern = re.compile(
        r"(?ms)^\*\*Зависимости приёмки Part II \(протокол №2\):\*\*\n\n"
        r"\| Критерий \| Блокирующий артефакт \| Срок \(протокол\) \|\n"
        r"\| --- \| --- \| --- \|\n"
        r"(?:\|[^\n]+\|\n)+",
    )
    return pattern.sub("", text)


def _remove_meeting_protocols_catalog_row(text: str) -> str:
    pattern = re.compile(
        r"(?ms)^\| \[meeting-protocols/\]\([^\)]+\) \|[^\n]*\n",
    )
    return pattern.sub("", text)


def _normalize_table_cell(cell: str) -> str:
    return cell.strip().strip("*").strip()


def _split_table_row(line: str) -> list[str]:
    parts = line.split("|")
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return parts


def _join_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _is_metadata_field_value_table(header_cells: list[str]) -> bool:
    if len(header_cells) != 2:
        return False
    return (
        _normalize_table_cell(header_cells[0]).lower() == "поле"
        and _normalize_table_cell(header_cells[1]).lower() == "значение"
    )


def _remove_status_column_from_table(table_lines: list[str]) -> list[str]:
    if not table_lines:
        return table_lines

    header_cells = _split_table_row(table_lines[0])
    if _is_metadata_field_value_table(header_cells):
        return table_lines

    status_idx = next(
        (
            idx
            for idx, cell in enumerate(header_cells)
            if _normalize_table_cell(cell).lower() == "статус"
        ),
        None,
    )
    if status_idx is None:
        return table_lines

    result: list[str] = []
    for line in table_lines:
        cells = _split_table_row(line)
        if len(cells) > status_idx:
            del cells[status_idx]
        result.append(_join_table_row(cells))
    return result


def _strip_workflow_status_columns(text: str) -> str:
    """Remove the «Статус» column from workflow tables (FR/UC/DOC-T, VII, etc.)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("|"):
            table_lines: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                table_lines.append(lines[i].rstrip("\n"))
                i += 1
            for processed in _remove_status_column_from_table(table_lines):
                out.append(processed + "\n")
        else:
            out.append(line)
            i += 1
    return "".join(out)


def _remove_status_legend_section(text: str) -> str:
    return _STATUS_LEGEND_SECTION.sub("", text)


def _remove_manual_toc_section(text: str) -> str:
    """Drop hand-written «Содержание»; customer export gets a generated TOC."""
    return _MANUAL_TOC_SECTION.sub("", text)


def _pandoc_inline_text(inlines) -> str:
    parts: list[str] = []
    for item in inlines:
        if not isinstance(item, dict):
            continue
        kind = item.get("t")
        content = item.get("c")
        if kind == "Str":
            parts.append(content)
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            parts.append(" ")
        elif kind == "Code":
            parts.append(content[1])
        elif kind in {"Strong", "Emph", "Underline", "Strikeout", "Superscript", "Subscript"}:
            parts.append(_pandoc_inline_text(content))
        elif kind == "Link":
            parts.append(_pandoc_inline_text(content[1]))
        elif kind == "Span":
            parts.append(_pandoc_inline_text(content[1]))
        elif kind == "Quoted":
            parts.append(_pandoc_inline_text(content[1]))
        elif kind == "Note":
            parts.append(_pandoc_inline_text(content))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _pandoc_headers(text: str) -> list[tuple[int, str, str]]:
    """Return ordered ``(level, anchor_id, plain_title)`` for each header."""
    result = subprocess.run(
        ["pandoc", "-f", PANDOC_MARKDOWN_FROM, "-t", "json"],
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    data = json.loads(result.stdout)
    headers: list[tuple[int, str, str]] = []

    def walk(blocks) -> None:
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("t") == "Header":
                level, ident, inlines = block["c"]
                header_id = ident[0] if ident else ""
                title = _pandoc_inline_text(inlines)
                headers.append((level, header_id, title))
            content = block.get("c")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        walk([item])
                    elif isinstance(item, list):
                        for sub in item:
                            if isinstance(sub, dict):
                                walk([sub])

    walk(data.get("blocks", []))
    return headers


def _should_include_h3_in_toc(title: str) -> bool:
    plain = title.strip()
    if any(plain.startswith(prefix) for prefix in _TOC_H3_EXCLUDE_PREFIXES):
        return False
    return bool(_TOC_H3_NUMBER.match(plain))


def _generate_toc_section(text: str) -> str:
    """Build static «Содержание» from document headings (links only, no body text)."""
    headers = _pandoc_headers(text)
    if not headers:
        return ""

    lines: list[str] = ["## Содержание", ""]
    appendix_items: list[tuple[str, str]] = []
    current_part: str | None = None

    for level, header_id, title in headers:
        if level == 1:
            if title.startswith("Приложение"):
                appendix_items.append((title, header_id))
                continue
            if title.startswith("Часть"):
                current_part = title
                lines.extend(["", f"### {title}", ""])
            continue

        if current_part is None or not header_id:
            continue

        if level == 2:
            lines.append(f"- [{title}](#{header_id})")
        elif level == 3 and _should_include_h3_in_toc(title):
            lines.append(f" - [{title}](#{header_id})")

    if appendix_items:
        lines.extend(["", "### Приложения", ""])
        for title, header_id in appendix_items:
            lines.append(f"- [{title}](#{header_id})")

    if len(lines) <= 2:
        return ""
    return "\n".join(lines).strip() + "\n\n---\n\n"


def _insert_generated_toc(text: str) -> str:
    toc = _generate_toc_section(text)
    if not toc:
        return text
    match = _FIRST_PART_HEADING.search(text)
    if not match:
        return text
    return text[: match.start()] + toc + text[match.start() :]


def _strip_protocol_anchors(text: str) -> str:
    """Drop in-document links whose anchor slug still contains «протокол»."""

    def _replace(match: re.Match[str]) -> str:
        link_text = match.group(1)
        url = match.group(2)
        if url.startswith("#") and re.search(r"протокол", url, re.IGNORECASE):
            return f"**{link_text}**"
        return match.group(0)

    return _MARKDOWN_LINK.sub(_replace, text)


def _neutralize_protocol_wordforms(text: str) -> str:
    for pattern, replacement in _NEUTRALIZE_PROTO_WORD:
        text = pattern.sub(replacement, text)
    return text


def _clean_inline(text: str) -> str:
    text = _PROTOCOL_SECTION_LINK.sub("", text)
    text = _MEETING_PROTOCOLS_LINK.sub("", text)
    for pattern, replacement in _INLINE_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _ORPHAN_SEMICOLON.sub(";", text)
    text = _TRAILING_SEMICOLON_SPACE.sub(r"\1", text)
    text = _DOUBLE_SPACE.sub(" ", text)
    text = re.sub(r"\|\s*,\s*,\s*", "| ", text)
    text = re.sub(r",\s*,\s+", ", ", text)
    return text


def prepare_customer_export(source: str) -> str:
    text = source

    text = _CUSTOMER_HIDE_BLOCK.sub("", text)
    text = _remove_internal_header_blocks(text)
    text = _remove_protocol_sections(text)
    text = _remove_customer_only_sections(text)
    text = _remove_internal_appendices(text)
    text = _TOC_PROTOCOL_LINE.sub("", text)
    text = _ORPHAN_TOC_BULLET.sub("", text)
    text = _TOC_APPENDIX_CD.sub("", text)
    text = _PROTOCOL_TABLE_ROW.sub("", text)
    text = _remove_internal_catalog_rows(text)
    text = _03_PROTOCOL_ASSIGNMENTS.sub("", text)
    text = _PROTOCOL_PARAGRAPH.sub("", text)
    text = _PROTOCOL_BULLET.sub("", text)
    text = _PROTOCOL_ASSIGNMENT_LINE.sub("", text)
    text = _SOURCE_PROTOCOL_LINE.sub("", text)
    text = _TRACING_PROTOCOL_BLOCK.sub("", text)
    text = _remove_v2_context_block(text)
    text = _remove_v2_dependencies_table(text)
    text = _remove_part_ii_dependencies_block(text)
    text = _remove_meeting_protocols_catalog_row(text)
    text = _simplify_i1_priority_list(text)
    text = _remove_status_legend_section(text)
    text = _remove_manual_toc_section(text)
    text = _strip_workflow_status_columns(text)
    text = _clean_inline(text)
    text = _strip_protocol_anchors(text)
    text = _normalize_bold_wrapped_source_links(text)
    text = _strip_internal_document_links(text)
    text = _clean_inline(text)
    text = _neutralize_protocol_wordforms(text)
    text = _cleanup_markdown_artifacts(text)

    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


def _normalize_anchor_key(anchor: str) -> str:
    key = anchor.lower().replace("ё", "е")
    for ch in "§–—":
        key = key.replace(ch, "")
    return key


def _pandoc_header_ids(text: str) -> set[str]:
    """Return GFM header identifiers Pandoc assigns to the document."""
    return {header_id for _, header_id, _ in _pandoc_headers(text) if header_id}


def _resolve_anchor(anchor: str, header_ids: set[str]) -> str | None:
    if anchor in header_ids:
        return anchor
    mapped = _ANCHOR_REMAP.get(anchor)
    if mapped and mapped in header_ids:
        return mapped
    norm = _normalize_anchor_key(anchor)
    for hid in header_ids:
        if _normalize_anchor_key(hid) == norm:
            return hid
    mapped_norm = _normalize_anchor_key(mapped) if mapped else ""
    if mapped_norm:
        for hid in header_ids:
            if _normalize_anchor_key(hid) == mapped_norm:
                return hid
    return None


def sync_markdown_anchors_for_docx(text: str) -> str:
    """Rewrite in-document [#anchor] links to match Pandoc GFM header IDs for Word hyperlinks."""
    header_ids = _pandoc_header_ids(text)

    def _replace(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        if not url.startswith("#"):
            return match.group(0)
        anchor = url[1:]
        if re.search(r"протокол", anchor, re.IGNORECASE):
            return f"**{label}**"
        resolved = _resolve_anchor(anchor, header_ids)
        if resolved:
            return f"[{label}](#{resolved})"
        return f"**{label}**"

    return _MARKDOWN_LINK.sub(_replace, text)


def prepare_docx_markdown(source: str, *, customer: bool = True) -> str:
    text = prepare_customer_export(source) if customer else source
    text = sync_markdown_anchors_for_docx(text)
    if customer:
        text = _insert_generated_toc(text)
    return text


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    customer = "--internal" not in sys.argv
    if len(args) != 2:
        print(
            "Usage: prepare_customer_export.py [--internal] <input.md> <output.md>",
            file=sys.stderr,
        )
        return 2

    src = Path(args[0])
    dst = Path(args[1])
    prepared = prepare_docx_markdown(src.read_text(encoding="utf-8"), customer=customer)
    dst.write_text(prepared, encoding="utf-8")
    mode = "customer" if customer else "internal+anchors"
    print(f"DOCX markdown prepared ({mode}): {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
