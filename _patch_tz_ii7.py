import pathlib,re
p=pathlib.Path(r"c:\sufler\docs\modules\ai-hub\tz-unified-v1.4.md")
lines=p.read_text(encoding="utf-8").splitlines()
for i,l in enumerate(lines):
    if l.startswith("| II-7 |"):
        old=l
        break
# build new notes - keep structure, update last column
parts=old.split("|")
# parts: empty, id, num, title, link, file, notes, empty
notes=parts[6].strip()
ver="v1.4.35"
# New notes incorporating v1.4.24, v1.4.25 and latest
new_notes=(
    f"**{ver}** - "
    "адаптивные брейкпоинты шапки АРМ (экраны 640/760 px); "
    "секция «История диалога» (UC-O8); "
    "кнопка «Аннотировать диалог» → «Аннотировать»; "
    "**v1.4.25** — заглушка меню «☰ Меню» (`toggleStatsDrawer`, `ArmStatsDrawer`, RBAC-вкладки); "
    "**v1.4.24** — 9 статусов оператора в **одной строке** (`flexWrap: nowrap`, `overflowX: auto`); "
    "`OperatorStatusPill` / `operatorStatusShade`: раздельные оттенки **9 статусов** (протокол 02.07 §2.1.9: онлайн, офлайн, обед, перерыв, обучение, совещание, звонок, офлайн-обработка, невидимый; inactive + active); "
    "`relevanceShade`: оттенки подсказок суфлёра по релевантности (≥90% / 80–89% / <80%); "
    "сдвигаемая панель «≡ Меню» (rail 52 px + контент 280 px, RBAC); "
    "scroll layout; collapse all/each; drag-resize; макет диалога §4.4"
)
parts[6]=f" {new_notes} "
new="|".join(parts)
if old==new:
    print("NO CHANGE")
else:
    lines[i]=new
    p.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("UPDATED line", i+1)
    print(new[:200]+"...")
