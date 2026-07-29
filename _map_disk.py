# -*- coding: utf-8 -*-
import json
import subprocess
from pathlib import Path

d = json.loads(Path("_transcript_inventory.json").read_text(encoding="utf-8"))
tracked = set(
    subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "a7daa4f"], text=True
    ).splitlines()
)
status = subprocess.check_output(
    ["git", "status", "--porcelain"], text=True, errors="replace"
)
modified = set()
untracked = set()
for line in status.splitlines():
    if not line:
        continue
    code = line[:2]
    path = line[3:].replace("\\", "/")
    if code.strip() == "??":
        untracked.add(path)
    else:
        modified.add(path)

lines = []
missing = differs = same = exists_new = 0
for area, items in sorted(d["by_area"].items()):
    lines.append(f"\n## {area} ({len(items)})")
    for it in sorted(items, key=lambda x: (x["status"], x["path"])):
        p = it["path"]
        on_disk = Path(p).exists()
        if it["status"] == "MODIFIED" and on_disk:
            diff = subprocess.run(
                ["git", "diff", "a7daa4f", "--", p],
                capture_output=True,
                text=True,
                errors="replace",
            )
            vs20 = "DIFFERS" if diff.stdout.strip() else "SAME_AS_20-07"
            if vs20 == "DIFFERS":
                differs += 1
            else:
                same += 1
        elif it["status"] == "NEW" and on_disk:
            vs20 = "EXISTS_ON_DISK"
            exists_new += 1
        elif not on_disk:
            vs20 = "MISSING_ON_DISK"
            missing += 1
        else:
            vs20 = "?"
        in_wt = (
            "M"
            if p in modified
            else (
                "U"
                if p in untracked
                or any(u.startswith(p.rstrip("/") + "/") for u in untracked)
                else "-"
            )
        )
        chats = ",".join(it["chats"])
        lines.append(
            f"{it['status']}\t{vs20}\tdisk={on_disk}\twt={in_wt}\tops={it['ops']}\t{p}\tchats={chats}"
        )

Path("_transcript_restore_map.txt").write_text("\n".join(lines), encoding="utf-8")
print(
    f"missing={missing} differs_from_20-07={differs} same_as_20-07={same} new_on_disk={exists_new} total={d['unique_files_total']}"
)

# Also dump area lists cleanly
for area, items in sorted(d["by_area"].items()):
    mod = [x["path"] for x in items if x["status"] == "MODIFIED"]
    new = [x["path"] for x in items if x["status"] == "NEW"]
    print(f"\n=== {area}: MODIFIED {len(mod)} NEW {len(new)} ===")
    print("-- MODIFIED --")
    for p in sorted(mod):
        print(p)
    print("-- NEW --")
    for p in sorted(new):
        print(p)
