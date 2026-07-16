#!/usr/bin/env python3
"""One-shot: refresh FR/UC in tz-unified-v1.3.md and write status log."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from _add_realizatsiya_column import TZ, main as regen_main  # noqa: E402

LOG = ROOT / "_regen_status.txt"

if __name__ == "__main__":
    regen_main()
    text = TZ.read_text(encoding="utf-8")
    LOG.write_text(
        f"lines={len(text.splitlines())}\n"
        f"effect={text.count('Целевой эффект')}\n"
        f"deploy_on_prem={text.count('deploy on-prem')}\n"
        f"fr_cc01_ok={'развёртывание модуля Контакт-центра в инфраструктуре банка' in text}\n"
        f"fr_und01_ok={'администратор базы знаний открывает Центр настроек Hub' in text}\n",
        encoding="utf-8",
    )
    print(LOG.read_text(encoding="utf-8"))
