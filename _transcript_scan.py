# -*- coding: utf-8 -*-
"""Scan agent transcripts for Write/StrReplace/ApplyPatch file paths after Jul 20 2026."""
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TRANSCRIPTS = Path(r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler\agent-transcripts")
REPO = Path(r"C:\Users\user\Desktop\sufler\sufler")
REPO_STR = str(REPO)
OUT = REPO / "_transcript_inventory.json"

# Priority folders + any with writes
FOCUS = {
    "c556b1db-b5a7-4419-aa78-4cc5fecd2a8f",
    "fbed0bf9-6a7a-4e02-ad7f-0f299ea2a808",
    "ecf0395e-a244-46e2-928d-211d19611b02",
    "0739a475-e036-4837-bc41-ecb49d85722c",
    "6ee6264c-e935-492a-8ca2-8c0eb0af5872",
}

TOOL_RE = re.compile(r'"name"\s*:\s*"(Write|StrReplace|ApplyPatch)"')
PATH_PATTERNS = [
    re.compile(r'"path"\s*:\s*"([^"]+)"'),
    re.compile(r'"file_path"\s*:\s*"([^"]+)"'),
    re.compile(r"\*\*\*\s+(?:Update|Add|Delete)\s+File:\s+([^\n\\]+)"),
    re.compile(r"@@\s+[^\n]*\n"),  # not a path
]
TS_RE = re.compile(r"<timestamp>([^<]+)</timestamp>")
TS_ALT = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')

REPO_NORM = REPO_STR.replace("\\", "/").lower()
REPO_ALT = "c:/users/user/desktop/sufler/sufler"


def normalize_path(p) -> str | None:
    if not p:
        return None
    p = str(p)
    p = p.replace("\\\\", "\\").replace("\\", "/")
    pl = p.lower()
    # skip non-repo / cursor internals
    if "agent-transcripts" in pl or ".cursor/projects" in pl:
        return None
    if pl.startswith(REPO_ALT) or pl.startswith(REPO_NORM):
        # strip absolute prefix
        for prefix in (REPO_ALT, REPO_NORM, "C:/Users/user/Desktop/sufler/sufler".lower()):
            if pl.startswith(prefix):
                rel = p[len(prefix) :].lstrip("/\\")
                return rel.replace("\\", "/")
    # relative paths that look like repo paths
    if p.startswith(("backend/", "frontend/", "tests/", "docs/", "infra/", ".github/", "scripts/", "_extracted/", "acceptance/", "load/", "benchmarks/")):
        return p.replace("\\", "/")
    if re.match(r"^(backend|frontend|tests|docs|infra|scripts|acceptance|load|benchmarks)[/\\]", p):
        return p.replace("\\", "/")
    return None


def parse_ts(s: str):
    s = s.strip()
    # e.g. Wednesday, Jul 27, 2026, 1:51 PM (UTC+3)
    for fmt in (
        "%A, %b %d, %Y, %I:%M %p (UTC+3)",
        "%A, %b %d, %Y, %I:%M %p (UTC)",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(s.replace(" (UTC+3)", " (UTC+3)").split(" (")[0] + ((" (UTC+3)" if "UTC+3" in s else "")), fmt) if False else None
        except Exception:
            pass
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})", s)
    if m:
        months = {n: i for i, n in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
        try:
            hour = 12
            hm = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", s, re.I)
            if hm:
                hour = int(hm.group(1)) % 12
                if hm.group(3).upper() == "PM":
                    hour += 12
                minute = int(hm.group(2))
            else:
                minute = 0
            return datetime(int(m.group(3)), months[m.group(1)], int(m.group(2)), hour, minute)
        except Exception:
            return datetime(int(m.group(3)), months[m.group(1)], int(m.group(2)))
    return None


def chat_id_from_path(fp: Path) -> str:
    parts = fp.parts
    try:
        idx = parts.index("agent-transcripts")
        return parts[idx + 1]
    except (ValueError, IndexError):
        return fp.parent.name


def extract_from_line(line: str):
    """Return list of (tool, path) from a jsonl line if it has write tools."""
    results = []
    if '"Write"' not in line and '"StrReplace"' not in line and "ApplyPatch" not in line:
        return results

    # Robust regex path (handles huge lines / odd JSON shapes)
    for m in re.finditer(
        r'"name"\s*:\s*"(Write|StrReplace|ApplyPatch)"\s*,\s*"input"\s*:\s*\{[^}]{0,500}?"(?:path|file_path)"\s*:\s*"((?:\\.|[^"\\])*)"',
        line,
    ):
        results.append((m.group(1), m.group(2).replace("\\\\", "\\").replace("\\/", "/")))

    # Also ApplyPatch *** Update File headers inside patch strings
    for m in re.finditer(r"\*\*\*\\\\?\s*(?:Update|Add|Delete)\\\\?\s+File:\\\\?\s+([^\\\"\\n]+)", line):
        results.append(("ApplyPatch", m.group(1).replace("\\\\", "\\")))
    for m in re.finditer(r"\*\*\*\s+(?:Update|Add|Delete)\s+File:\s+([^\\\"\\n]+)", line):
        results.append(("ApplyPatch", m.group(1)))

    try:
        obj = json.loads(line)
    except Exception:
        return results

    msg = obj.get("message")
    if isinstance(msg, str):
        return results
    if not isinstance(msg, dict):
        return results
    content = msg.get("content")
    if not isinstance(content, list):
        return results

    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "tool_use":
            continue
        name = part.get("name") or ""
        inp = part.get("input") or {}
        if not isinstance(inp, dict):
            continue
        if name in ("Write", "StrReplace"):
            path = inp.get("path") or inp.get("file_path")
            if path:
                results.append((name, path))
        elif name == "ApplyPatch":
            patch = inp.get("patch") or inp.get("input") or ""
            if isinstance(patch, str):
                for m in re.finditer(r"\*\*\*\s+(?:Update|Add|Delete)\s+File:\s+(.+)", patch):
                    results.append((name, m.group(1).strip()))
            path = inp.get("path") or inp.get("file_path")
            if path:
                results.append((name, path))
    return results


def first_user_ts(fp: Path):
    try:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 5:
                    break
                m = TS_RE.search(line)
                if m:
                    return parse_ts(m.group(1)), m.group(1)
    except Exception:
        pass
    return None, None


def main():
    # files in a7daa4f
    try:
        tracked = set(
            subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", "a7daa4f"],
                cwd=str(REPO),
                text=True,
            ).splitlines()
        )
    except Exception as e:
        tracked = set()
        print("WARN git ls-tree failed:", e)

    # map chat -> dates
    chat_meta = {}
    all_jsonl = list(TRANSCRIPTS.rglob("*.jsonl"))
    for fp in all_jsonl:
        cid = chat_id_from_path(fp)
        if "subagents" in str(fp):
            continue
        ts, raw = first_user_ts(fp)
        if cid not in chat_meta or (ts and (chat_meta[cid]["ts"] is None or ts < chat_meta[cid]["ts"])):
            chat_meta[cid] = {"ts": ts, "raw": raw, "file": str(fp)}

    # extract writes
    writes_by_file = defaultdict(list)  # path -> [{chat, tool, line_hint}]
    writes_by_chat = defaultdict(set)
    chat_write_counts = defaultdict(int)

    for fp in all_jsonl:
        cid = chat_id_from_path(fp)
        meta = chat_meta.get(cid, {})
        ts = meta.get("ts")
        # Keep Jul 21+ OR unknown date for focus chats; exclude clearly pre-Jul-21 if known
        if ts and ts < datetime(2026, 7, 21) and cid not in FOCUS:
            # still include if focus; for others skip pre-21
            continue
        if ts and ts < datetime(2026, 7, 20) and cid not in FOCUS:
            continue

        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    for tool, path in extract_from_line(line):
                        rel = normalize_path(path)
                        if not rel:
                            # keep absolute under sufler even if normalize failed oddly
                            p2 = path.replace("\\", "/")
                            if "sufler/sufler/" in p2.lower():
                                idx = p2.lower().rfind("sufler/sufler/")
                                rel = p2[idx + len("sufler/sufler/") :]
                            else:
                                continue
                        # skip transcript scan artifacts
                        if rel.startswith("_transcript_") or rel == "_transcript_scan.py":
                            continue
                        chat_write_counts[cid] += 1
                        writes_by_chat[cid].add(rel)
                        writes_by_file[rel].append(
                            {
                                "chat": cid,
                                "tool": tool,
                                "file": str(fp),
                                "lineno": lineno,
                                "chat_ts": meta.get("raw"),
                            }
                        )
        except Exception as e:
            print("ERR", fp, e)

    # Also scan Shell redirects that write to repo (Out-File, Set-Content, > path)
    shell_writes = defaultdict(list)
    shell_path_re = re.compile(
        r"(?:Out-File|Set-Content|Add-Content|Redirect|>>?)\s+[\"']?([^\"'\s]+\.(?:py|ts|tsx|js|jsx|yml|yaml|json|md|txt|toml|cfg|ini|env|sh|ps1|css|html))",
        re.I,
    )
    # Too noisy — skip broad shell scan; focus on known Write tools

    # Classify
    areas = defaultdict(list)
    for rel in sorted(writes_by_file):
        if rel.startswith("backend/"):
            area = "backend"
        elif rel.startswith("frontend/"):
            area = "frontend"
        elif rel.startswith("tests/") or "/test_" in rel or rel.startswith("acceptance/") or rel.startswith("load/") or rel.startswith("benchmarks/"):
            area = "tests"
        elif rel.startswith("docs/") or rel.startswith("_extracted/"):
            area = "docs"
        elif rel.startswith("infra/") or rel.startswith("docker") or "compose" in rel:
            area = "infra"
        elif rel.startswith(".github/"):
            area = "github"
        else:
            area = "other"
        is_tracked = rel in tracked
        areas[area].append(
            {
                "path": rel,
                "status": "MODIFIED" if is_tracked else "NEW",
                "chats": sorted({e["chat"] for e in writes_by_file[rel]}),
                "ops": len(writes_by_file[rel]),
            }
        )

    # Key file last change summaries — grab nearby assistant text after last write
    key_files = [
        "backend/sufler/settings.py",
        "backend/sufler/urls.py",
        "frontend/src/App.tsx",
        "frontend/package.json",
        "package.json",
        ".github/workflows/ci.yml",
        "infra/docker-compose.yml",
        "docker-compose.yml",
        "backend/hub/views.py",
        "backend/ingest/pipeline.py",
        "backend/auth/roles.py",
        "docs/api/postman_collection.json",
        ".github/workflows/deploy-test.yml",
    ]
    key_summaries = {}
    for kf in key_files:
        entries = writes_by_file.get(kf) or []
        if not entries:
            continue
        last = entries[-1]
        # read around that line for assistant summary after
        summary = None
        try:
            with open(last["file"], "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            # look forward for role:assistant text without tool_use only
            for j in range(last["lineno"], min(last["lineno"] + 30, len(lines))):
                try:
                    obj = json.loads(lines[j])
                except Exception:
                    continue
                if obj.get("role") != "assistant":
                    continue
                content = (obj.get("message") or {}).get("content") or []
                texts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts.append(part.get("text") or "")
                blob = "\n".join(texts).strip()
                if blob and len(blob) > 40:
                    summary = blob[:800]
                    break
        except Exception as e:
            summary = f"(error reading: {e})"
        key_summaries[kf] = {
            "last_chat": last["chat"],
            "last_tool": last["tool"],
            "chat_ts": last.get("chat_ts"),
            "ops_total": len(entries),
            "summary_snippet": summary,
        }

    # Chat-only content: look for large code blocks in assistant text without subsequent Write of same file
    # Heuristic: fenced code blocks mentioning filenames
    chat_only_hints = []

    result = {
        "tracked_count_a7daa4f": len(tracked),
        "chats_with_writes_jul21plus": {
            cid: {
                "count": chat_write_counts[cid],
                "unique_files": len(writes_by_chat[cid]),
                "ts": chat_meta.get(cid, {}).get("raw"),
                "files_sample": sorted(writes_by_chat[cid])[:40],
            }
            for cid in sorted(chat_write_counts, key=lambda c: -chat_write_counts[c])
        },
        "all_chat_meta_jul21plus": {
            cid: {"ts": m.get("raw"), "file": m.get("file")}
            for cid, m in sorted(chat_meta.items(), key=lambda x: (x[1].get("ts") or datetime.min))
            if m.get("ts") is None or m["ts"] >= datetime(2026, 7, 21)
        },
        "unique_files_total": len(writes_by_file),
        "by_area": {k: v for k, v in areas.items()},
        "key_summaries": key_summaries,
        "focus_chats": {
            cid: {
                "ts": chat_meta.get(cid, {}).get("raw"),
                "write_ops": chat_write_counts.get(cid, 0),
                "unique_files": sorted(writes_by_chat.get(cid, [])),
            }
            for cid in FOCUS
        },
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print("unique files", len(writes_by_file))
    print("chats with writes:", len(chat_write_counts))
    for cid, n in sorted(chat_write_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cid}: {n} ops, {len(writes_by_chat[cid])} files, ts={chat_meta.get(cid,{}).get('raw')}")


if __name__ == "__main__":
    main()
