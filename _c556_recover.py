# -*- coding: utf-8 -*-
"""Analyze recoverability of post-20-07 edits from c556 transcript."""
import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(r"C:\Users\user\Desktop\sufler\sufler")
TRANS = Path(
    r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-sufler-sufler\agent-transcripts"
    r"\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f\c556b1db-b5a7-4419-aa78-4cc5fecd2a8f.jsonl"
)
inv = json.loads((REPO / "_transcript_inventory.json").read_text(encoding="utf-8"))

# Last tool type per file in c556
last_tool = {}
last_write_contents = {}  # path -> full contents if last op was Write
ops_by_file = defaultdict(lambda: {"Write": 0, "StrReplace": 0})

with TRANS.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        if '"Write"' not in line and '"StrReplace"' not in line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "tool_use":
                continue
            name = part.get("name")
            if name not in ("Write", "StrReplace"):
                continue
            inp = part.get("input") or {}
            if not isinstance(inp, dict):
                continue
            path = str(inp.get("path") or "").replace("\\", "/")
            if "sufler/sufler/" in path.lower():
                idx = path.lower().rfind("sufler/sufler/")
                rel = path[idx + len("sufler/sufler/") :]
            elif path.startswith(("backend/", "frontend/", "tests/", "docs/", "infra/", ".github/", "scripts/")):
                rel = path
            else:
                continue
            ops_by_file[rel][name] += 1
            last_tool[rel] = name
            if name == "Write":
                last_write_contents[rel] = inp.get("contents")

status = subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=REPO, text=True, errors="replace"
)
untracked_roots = set()
for line in status.splitlines():
    if line.startswith("??"):
        untracked_roots.add(line[3:].replace("\\", "/").rstrip("/"))

def is_untracked(p: str) -> bool:
    if p in untracked_roots:
        return True
    for u in untracked_roots:
        if p.startswith(u.rstrip("/") + "/") or u.startswith(p.rstrip("/") + "/"):
            return True
    # check path itself
    return (REPO / p).exists() and subprocess.run(
        ["git", "ls-files", "--error-unmatch", p],
        cwd=REPO,
        capture_output=True,
    ).returncode != 0

# Classification for c556 files
c556_files = set(inv["focus_chats"]["c556b1db-b5a7-4419-aa78-4cc5fecd2a8f"]["unique_files"])
# full list may be truncated in focus - use by_area chats
c556_all = set()
for items in inv["by_area"].values():
    for it in items:
        if "c556b1db-b5a7-4419-aa78-4cc5fecd2a8f" in it["chats"]:
            c556_all.add(it["path"])

tracked = set(
    subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "a7daa4f"], cwd=REPO, text=True
    ).splitlines()
)

recover_write = []  # last op Write -> full content in transcript
need_replay = []  # last op StrReplace on tracked -> need chain replay
new_present = []
new_missing = []
mod_same = []

for p in sorted(c556_all):
    is_mod = p in tracked
    exists = (REPO / p).exists()
    lt = last_tool.get(p, "?")
    if is_mod:
        mod_same.append(p)
        if lt == "Write" and p in last_write_contents:
            recover_write.append(p)
        else:
            need_replay.append(p)
    else:
        if exists:
            new_present.append((p, lt, is_untracked(p)))
        else:
            new_missing.append(p)

# Save last Write payloads for key modified files
key = [
    "backend/sufler/settings.py",
    "backend/sufler/urls.py",
    "frontend/src/App.tsx",
    "frontend/package.json",
    ".github/workflows/ci.yml",
    "infra/docker-compose.yml",
    "backend/hub/views.py",
    "backend/auth/roles.py",
    ".github/workflows/deploy-test.yml",
    "backend/core/metrics.py",
    "backend/assistant/chat.py",
]
key_info = {}
for p in key:
    key_info[p] = {
        "in_a7daa4f": p in tracked,
        "exists": (REPO / p).exists(),
        "last_tool": last_tool.get(p),
        "ops": ops_by_file.get(p),
        "has_full_write_payload": p in last_write_contents,
        "write_len": len(last_write_contents[p]) if p in last_write_contents else 0,
        "untracked": is_untracked(p) if (REPO / p).exists() else None,
    }

out = {
    "c556_unique_files": len(c556_all),
    "mod_tracked_count": len(mod_same),
    "new_present": len(new_present),
    "new_missing": len(new_missing),
    "recoverable_via_last_Write": len(recover_write),
    "need_StrReplace_replay": len(need_replay),
    "recover_write_sample": recover_write[:40],
    "need_replay_sample": need_replay[:40],
    "new_missing_list": new_missing,
    "key_info": key_info,
    "new_present_untracked": sum(1 for _, _, u in new_present if u),
    "new_present_tracked_somehow": sum(1 for _, _, u in new_present if not u),
}
(REPO / "_c556_recoverability.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Dump full lists
lines = ["# MODIFIED tracked in c556 (content now == a7daa4f; post-20-07 edits LOST on disk)"]
for p in sorted(mod_same):
    lines.append(f"{last_tool.get(p,'?'):10}  {p}")
lines.append("\n# NEW in c556 still on disk")
for p, lt, u in sorted(new_present):
    lines.append(f"{lt:10}  untracked={u}  {p}")
lines.append("\n# NEW in c556 MISSING")
for p in sorted(new_missing):
    lines.append(p)
(REPO / "_c556_file_status.txt").write_text("\n".join(lines), encoding="utf-8")

print(json.dumps({k: out[k] for k in out if k != "key_info"}, ensure_ascii=False, indent=2))
print("--- key_info ---")
print(json.dumps(key_info, ensure_ascii=False, indent=2))
