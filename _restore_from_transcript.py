# -*- coding: utf-8 -*-
"""Restore post-20-07 edits via chat transcript replay only (no Cursor history)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\user\Desktop\sufler\sufler")
STATUS_FILE = REPO / "_c556_file_status.txt"
REPORT = REPO / "_restore_transcript_report.txt"

# Chronological order: Jul 21 first, then Jul 27 main implementation
TRANSCRIPTS = [
    Path(
        r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
        r"\agent-transcripts\ab1a12a4-6fdf-456f-ad0a-b495c4fae664"
        r"\ab1a12a4-6fdf-456f-ad0a-b495c4fae664.jsonl"
    ),
    Path(
        r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
        r"\agent-transcripts\badafbfe-2638-4aa1-bd87-a5f58dbb7c3a"
        r"\badafbfe-2638-4aa1-bd87-a5f58dbb7c3a.jsonl"
    ),
    Path(
        r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
        r"\agent-transcripts\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f"
        r"\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f.jsonl"
    ),
]


def to_rel(path: str) -> str:
    path = path.replace("\\", "/")
    marker = "/sufler/sufler/"
    if marker in path:
        return path.split(marker, 1)[1]
    repo = str(REPO).replace("\\", "/")
    if path.startswith(repo):
        return path[len(repo) :].lstrip("/")
    return path.lstrip("./")


def load_targets() -> list[str]:
    files: list[str] = []
    for line in STATUS_FILE.read_text(encoding="utf-8").splitlines():
        if "untracked=True" in line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("Write", "StrReplace"):
            files.append(parts[-1].replace("\\", "/"))
    extras = [
        "README.md",
        "docs/modules/ai-hub/README.md",
        "frontend/src/auth/usePortalAuth.ts",
        "frontend/vite.config.ts",
        "infra/.env.example",
        "infra/README.md",
        "infra/docker-compose.yml",
        "frontend/README.md",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for f in files + extras:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def git_show_text(rel: str) -> str | None:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    return raw.decode("utf-8", errors="replace")


def extract_ops(transcript: Path) -> list[tuple[str, str, dict]]:
    ops: list[tuple[str, str, dict]] = []
    if not transcript.exists():
        return ops
    with transcript.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("role") != "assistant":
                continue
            content = (obj.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue
                name = part.get("name")
                inp = part.get("input") or {}
                if name == "Write" and "contents" in inp and inp.get("path"):
                    ops.append(("Write", to_rel(inp["path"]), inp))
                elif (
                    name == "StrReplace"
                    and inp.get("path")
                    and "old_string" in inp
                    and "new_string" in inp
                ):
                    ops.append(("StrReplace", to_rel(inp["path"]), inp))
    return ops


def main() -> int:
    targets = set(load_targets())
    all_ops: list[tuple[str, str, dict]] = []
    for t in TRANSCRIPTS:
        all_ops.extend(extract_ops(t))

    # Filter ops to targets only, preserve order
    file_ops: dict[str, list[tuple[str, dict]]] = {rel: [] for rel in targets}
    for tool, path, inp in all_ops:
        if path in file_ops:
            file_ops[path].append((tool, inp))

    lines: list[str] = []
    restored = 0
    nochange = 0
    missing = 0

    for rel in sorted(targets):
        base = git_show_text(rel)
        if base is None:
            lines.append(f"SKIP not-in-HEAD: {rel}")
            missing += 1
            continue
        text = base
        writes = ok = fail = 0
        for tool, inp in file_ops.get(rel, []):
            if tool == "Write":
                text = inp["contents"]
                writes += 1
            else:
                old, new = inp["old_string"], inp["new_string"]
                replace_all = bool(inp.get("replace_all"))
                if old not in text:
                    fail += 1
                    continue
                text = text.replace(old, new) if replace_all else text.replace(old, new, 1)
                ok += 1

        if text == base:
            lines.append(f"NOCHANGE ops={len(file_ops.get(rel, []))} w={writes} ok={ok} fail={fail}: {rel}")
            nochange += 1
            continue

        path = REPO / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write as UTF-8 LF (git will normalize on commit as needed)
        data = text.encode("utf-8")
        if not data.endswith(b"\n") and b"\n" in data:
            data += b"\n"
        path.write_bytes(data)
        restored += 1
        delta = len(text) - len(base)
        lines.append(f"OK w={writes} ok={ok} fail={fail} delta={delta:+d}: {rel}")

    summary = [
        f"targets={len(targets)} restored={restored} nochange={nochange} missing={missing}",
        "",
        *lines,
    ]
    REPORT.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(summary[0])
    # show failures / interesting
    for line in lines:
        if line.startswith("OK") or "fail=" in line:
            # print all OK and anything with fails
            if line.startswith("OK") and "fail=0" in line:
                continue
            print(line)
    fails = [l for l in lines if "fail=" in l and not l.startswith("NOCHANGE")]
    fail_nonzero = [l for l in fails if "fail=0" not in l.split(":")[0]]
    print(f"files_with_failed_replaces={len(fail_nonzero)}")
    for l in fail_nonzero:
        print(l)
    print(f"report={REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
