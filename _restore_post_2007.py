# -*- coding: utf-8 -*-
"""Restore post-20-07 edits to tracked files from Cursor Local History + chat transcript."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO = Path(r"C:\Users\user\Desktop\sufler\sufler")
HISTORY = Path(os.environ["APPDATA"]) / "Cursor" / "User" / "History"
TRANSCRIPT = Path(
    r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
    r"\agent-transcripts\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f"
    r"\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f.jsonl"
)
# Also replay Jul 21 chats that touched tracked files
EXTRA_TRANSCRIPTS = [
    Path(
        r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
        r"\agent-transcripts\badafbfe-2638-4aa1-bd87-a5f58dbb7c3a"
        r"\badafbfe-2638-4aa1-bd87-a5f58dbb7c3a.jsonl"
    ),
    Path(
        r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler"
        r"\agent-transcripts\ab1a12a4-6fdf-456f-ad0a-b495c4fae664"
        r"\ab1a12a4-6fdf-456f-ad0a-b495c4fae664.jsonl"
    ),
]
STATUS_FILE = REPO / "_c556_file_status.txt"
REPORT = REPO / "_restore_post_2007_report.txt"


def git_show(rel: str) -> bytes | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel.replace(chr(92), '/')}"],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def load_modified_list() -> list[str]:
    files: list[str] = []
    for line in STATUS_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if "untracked=True" in line:
            continue
        if line.strip().startswith("Write") or line.strip().startswith("StrReplace"):
            # formats: "StrReplace  path" or "Write       path"
            parts = line.split()
            if len(parts) >= 2:
                files.append(parts[-1].replace("\\", "/"))
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def build_history_index() -> dict[str, list[tuple[int, Path]]]:
    """Map repo-relative path -> [(timestamp, file_path), ...] newest last."""
    idx: dict[str, list[tuple[int, Path]]] = {}
    repo_uri_prefix = "file:///c%3A/Users/user/Desktop/sufler/sufler/"
    repo_uri_prefix2 = "file:///C:/Users/user/Desktop/sufler/sufler/"
    for folder in HISTORY.iterdir():
        if not folder.is_dir():
            continue
        entries_path = folder / "entries.json"
        if not entries_path.exists():
            continue
        try:
            data = json.loads(entries_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        resource = data.get("resource") or ""
        rel = None
        if resource.lower().startswith(repo_uri_prefix.lower()):
            rel = unquote(resource[len(repo_uri_prefix) :])
        elif resource.replace("\\", "/").startswith(repo_uri_prefix2):
            rel = unquote(resource[len(repo_uri_prefix2) :])
        else:
            # try generic parse
            m = re.search(r"/sufler/sufler/(.+)$", unquote(resource).replace("\\", "/"))
            if m:
                rel = m.group(1)
        if not rel:
            continue
        rel = rel.replace("\\", "/")
        for e in data.get("entries") or []:
            eid = e.get("id")
            ts = int(e.get("timestamp") or 0)
            if not eid:
                continue
            fp = folder / eid
            if fp.exists():
                idx.setdefault(rel, []).append((ts, fp))
    for rel in idx:
        idx[rel].sort(key=lambda x: x[0])
    return idx


def extract_tool_ops(transcript: Path) -> list[tuple[str, str, dict]]:
    """Return list of (tool, path, args) in order."""
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
            msg = obj.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "tool_use":
                    continue
                name = part.get("name")
                inp = part.get("input") or {}
                if name == "Write":
                    path = (inp.get("path") or "").replace("\\", "/")
                    if "/sufler/sufler/" in path:
                        path = path.split("/sufler/sufler/", 1)[1]
                    elif path.startswith(str(REPO).replace("\\", "/")):
                        path = path[len(str(REPO).replace("\\", "/")) :].lstrip("/")
                    if path and "contents" in inp:
                        ops.append(("Write", path, inp))
                elif name == "StrReplace":
                    path = (inp.get("path") or "").replace("\\", "/")
                    if "/sufler/sufler/" in path:
                        path = path.split("/sufler/sufler/", 1)[1]
                    elif path.startswith(str(REPO).replace("\\", "/")):
                        path = path[len(str(REPO).replace("\\", "/")) :].lstrip("/")
                    if path and "old_string" in inp and "new_string" in inp:
                        ops.append(("StrReplace", path, inp))
                elif name == "ApplyPatch":
                    # skip complex patches for now; rare for lost files
                    continue
    return ops


def apply_str_replace(text: str, old: str, new: str, replace_all: bool = False) -> tuple[str, bool]:
    if old not in text:
        return text, False
    if replace_all:
        return text.replace(old, new), True
    return text.replace(old, new, 1), True


def replay_file(rel: str, ops: list[tuple[str, str, dict]], base: str) -> tuple[str, dict]:
    text = base
    stats = {"writes": 0, "replaces_ok": 0, "replaces_fail": 0}
    for tool, path, inp in ops:
        if path != rel:
            continue
        if tool == "Write":
            text = inp["contents"]
            if not text.endswith("\n") and "\n" in text:
                # keep as-is from transcript
                pass
            stats["writes"] += 1
        elif tool == "StrReplace":
            text2, ok = apply_str_replace(
                text,
                inp["old_string"],
                inp["new_string"],
                bool(inp.get("replace_all")),
            )
            if ok:
                text = text2
                stats["replaces_ok"] += 1
            else:
                stats["replaces_fail"] += 1
    return text, stats


def main() -> int:
    modified = load_modified_list()
    # also add Jul 21 tracked files that may not be in c556 list
    for extra in [
        "README.md",
        "docs/modules/ai-hub/README.md",
        "frontend/src/auth/usePortalAuth.ts",
        "frontend/vite.config.ts",
        "infra/.env.example",
        "infra/README.md",
        "infra/docker-compose.yml",
        "frontend/README.md",
    ]:
        if extra not in modified:
            modified.append(extra)

    hist = build_history_index()
    all_ops: list[tuple[str, str, dict]] = []
    for t in EXTRA_TRANSCRIPTS + [TRANSCRIPT]:
        all_ops.extend(extract_tool_ops(t))

    lines: list[str] = []
    restored_hist = 0
    restored_replay = 0
    skipped = 0
    failed: list[str] = []

    for rel in modified:
        disk = REPO / rel
        head_bytes = git_show(rel)
        if head_bytes is None:
            lines.append(f"SKIP (not in HEAD): {rel}")
            skipped += 1
            continue
        # normalize newlines for compare
        head_text = head_bytes.decode("utf-8", errors="replace")
        # prefer LF for python sources; keep as decoded
        chosen: str | None = None
        source = None

        # 1) Cursor local history: newest entry that differs from HEAD
        if rel in hist:
            for ts, fp in reversed(hist[rel]):
                try:
                    cand = fp.read_bytes().decode("utf-8", errors="replace")
                except Exception:
                    continue
                if cand != head_text and cand.strip():
                    chosen = cand
                    source = f"history:{fp.parent.name}/{fp.name} ts={ts}"
                    break

        # 2) Transcript replay if history missing or same as HEAD
        if chosen is None:
            replayed, stats = replay_file(rel, all_ops, head_text)
            if replayed != head_text:
                chosen = replayed
                source = (
                    f"transcript_replay writes={stats['writes']} "
                    f"ok={stats['replaces_ok']} fail={stats['replaces_fail']}"
                )
            elif stats["writes"] or stats["replaces_ok"] or stats["replaces_fail"]:
                lines.append(
                    f"NOCHANGE after replay ({stats}): {rel}"
                )
                skipped += 1
                continue
            else:
                lines.append(f"NOOPS: {rel}")
                skipped += 1
                continue

        if chosen == head_text:
            lines.append(f"SAME: {rel}")
            skipped += 1
            continue

        disk.parent.mkdir(parents=True, exist_ok=True)
        # preserve newline style roughly: if head used CRLF keep CRLF
        if b"\r\n" in head_bytes and "\r\n" not in chosen:
            to_write = chosen.replace("\n", "\r\n").encode("utf-8")
        else:
            to_write = chosen.encode("utf-8")
        disk.write_bytes(to_write)
        if source and source.startswith("history"):
            restored_hist += 1
        else:
            restored_replay += 1
        lines.append(f"OK [{source}] {rel} (+{len(chosen) - len(head_text)} chars)")

    summary = [
        f"modified_targets={len(modified)}",
        f"restored_from_history={restored_hist}",
        f"restored_from_transcript={restored_replay}",
        f"skipped={skipped}",
        f"failed={len(failed)}",
        "",
        *lines,
    ]
    REPORT.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary[:30]))
    print(f"... full report: {REPORT}")
    print(f"TOTAL restored: {restored_hist + restored_replay}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
