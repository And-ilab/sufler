#!/usr/bin/env python3
"""Dump FR map and regenerate tz-unified-v1.3.md in one shot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fr_realizatsiya import FR  # noqa: E402
from _add_realizatsiya_column import TZ, main  # noqa: E402

CACHE = ROOT / "fr_impl_cache.json"
STATUS = ROOT / "_regen_status.txt"

if __name__ == "__main__":
    CACHE.write_text(json.dumps(FR, ensure_ascii=False, indent=2), encoding="utf-8")
    main()
    text = TZ.read_text(encoding="utf-8")
    STATUS.write_text(
        "\n".join(
            [
                f"fr_entries={len(FR)}",
                f"lines={len(text.splitlines())}",
                f"effect={text.count('Целевой эффект')}",
                f"deploy_on_prem={text.count('deploy on-prem')}",
                f"admin_kb_hub={text.count('admin KB, Hub UI')}",
                f"fr_und01_ok={'администратор базы знаний открывает Центр настроек Hub' in text}",
            ]
        ),
        encoding="utf-8",
    )
