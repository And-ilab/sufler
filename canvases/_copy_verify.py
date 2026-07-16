import json
import os
import shutil

SRC_DIR = r"C:\Users\bkp2.LAPTOP-714KMOB9\.cursor\projects\c-sufler\canvases"
DEST_DIR = r"c:\sufler\canvases"
FILES = [
    "online-chat-mockups.canvas.tsx",
    "online-chat-mockups.canvas.data.json",
]
TARGET_VERSION = "v1.4.43"

os.makedirs(DEST_DIR, exist_ok=True)

copy_results = {}
for name in FILES:
    src = os.path.join(SRC_DIR, name)
    dst = os.path.join(DEST_DIR, name)
    if not os.path.isfile(src):
        copy_results[name] = {"ok": False, "error": f"missing source: {src}"}
        continue
    shutil.copy2(src, dst)
    copy_results[name] = {
        "ok": os.path.isfile(dst),
        "size": os.path.getsize(dst) if os.path.isfile(dst) else None,
    }

tsx_path = os.path.join(DEST_DIR, "online-chat-mockups.canvas.tsx")
version_line = None
first_40 = []
if os.path.isfile(tsx_path):
    with open(tsx_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 40:
                break
            stripped = line.rstrip("\n")
            first_40.append(stripped)
            if "CANVAS_MOCKUP_VERSION" in line:
                version_line = stripped

version_ok = version_line is not None and TARGET_VERSION in version_line

json_path = os.path.join(DEST_DIR, "online-chat-mockups.canvas.data.json")
json_updated = False
canvas_build = None
if os.path.isfile(json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    canvas_build = data.get("_canvasBuild")
    if canvas_build != TARGET_VERSION:
        data["_canvasBuild"] = TARGET_VERSION
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        json_updated = True
        canvas_build = TARGET_VERSION

out_path = os.path.join(DEST_DIR, "_copy_verify_result.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("COPY_RESULTS\n")
    for name, info in copy_results.items():
        f.write(f"{name}: ok={info.get('ok')} size={info.get('size')} err={info.get('error', '')}\n")
    f.write(f"\nTSX_SIZE={os.path.getsize(tsx_path) if os.path.isfile(tsx_path) else None}\n")
    f.write(f"VERSION_LINE={version_line}\n")
    f.write(f"VERSION_OK={version_ok}\n")
    f.write(f"JSON_CANVAS_BUILD={canvas_build}\n")
    f.write(f"JSON_UPDATED={json_updated}\n")
    f.write("\nFIRST_40_LINES\n")
    for i, line in enumerate(first_40, 1):
        f.write(f"{i:3}|{line}\n")

print("done")
