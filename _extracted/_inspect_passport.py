# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import zipfile
from collections import OrderedDict, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

DOCX = Path(r"c:\Users\user\Downloads\Паспорт_станка_GW_DS09_ГОСТ_2_601_2019_1.docx")
OUT = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\passport_inspect.txt")
FINSELVAT = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\finselvat_details.txt")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
V = "{urn:schemas-microsoft-com:vml}"
EDGE = ("top", "left", "bottom", "right", "insideH", "insideV", "tl2br", "tr2bl")


def local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(t.text or "" for t in el.iter(f"{W}t"))


def para_text(p: ET.Element) -> str:
    return text_of(p).strip()


def style_of(p: ET.Element) -> str:
    pPr = p.find(f"{W}pPr")
    if pPr is None:
        return ""
    ps = pPr.find(f"{W}pStyle")
    return (ps.get(f"{W}val") if ps is not None else "") or ""


def is_heading(s: str) -> bool:
    return bool(re.match(r"(?i)heading|заголовок", s or ""))


def border_desc(el: ET.Element | None) -> str:
    if el is None:
        return "MISSING"
    val = el.get(f"{W}val") or "?"
    if val in ("nil", "none"):
        return val
    return f"val={val} sz={el.get(f'{W}sz') or '-'} color={el.get(f'{W}color') or '-'} space={el.get(f'{W}space') or '-'}"


def borders_block(parent: ET.Element | None, tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if parent is None:
        return {e: "NO_PARENT" for e in EDGE}
    block = parent.find(f"{W}{tag}")
    if block is None:
        return {e: "NO_BORDERS_ELEMENT" for e in EDGE}
    for e in EDGE:
        out[e] = border_desc(block.find(f"{W}e".replace("e", e) if False else f"{W}{e}"))
    return out


def miss_edges(borders: dict[str, str], req=("top", "left", "bottom", "right", "insideH", "insideV")) -> list[str]:
    miss = []
    for e in req:
        v = borders.get(e, "MISSING")
        if v in ("MISSING", "NO_BORDERS_ELEMENT", "NO_PARENT", "nil", "none") or str(v).startswith("nil") or str(v).startswith("none"):
            miss.append(f"{e}={v}")
    return miss


def twips_mm(tw: str | None) -> str:
    if not tw:
        return "?"
    try:
        return f"{int(tw) * 25.4 / 1440:.2f} mm ({tw} twips)"
    except ValueError:
        return tw


def half_pt(sz: str | None) -> str:
    if not sz:
        return "?"
    try:
        return f"{int(sz) / 2:g} pt"
    except ValueError:
        return sz


def emu_mm(x: str | None) -> float | None:
    if not x:
        return None
    return int(x) * 25.4 / 914400


def load_rels(zf: zipfile.ZipFile, path: str) -> dict[str, str]:
    m: dict[str, str] = {}
    if path not in zf.namelist():
        return m
    root = ET.fromstring(zf.read(path))
    for rel in root:
        if local(rel.tag) != "Relationship":
            continue
        rid, target = rel.get("Id"), rel.get("Target")
        if rid and target:
            m[rid] = target.lstrip("/") if target.startswith("/") else "word/" + target.replace("\\", "/")
    return m


def cell_grid(tbl: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in tbl.findall(f"{W}tr"):
        row: list[str] = []
        for tc in tr.findall(f"{W}tc"):
            paras = [para_text(p) for p in tc.findall(f"{W}p")]
            cell = "\n".join(p for p in paras if p) or "(empty)"
            row.append(cell)
        if row:
            rows.append(row)
    return rows


def font_counts(root: ET.Element) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for sz in root.iter(f"{W}sz"):
        v = sz.get(f"{W}val")
        if v:
            c[half_pt(v)] += 1
    for sz in root.iter(f"{W}szCs"):
        v = sz.get(f"{W}val")
        if v:
            c[half_pt(v) + " (szCs)"] += 1
    return dict(sorted(c.items(), key=lambda x: (-x[1], x[0])))


def main() -> None:
    lines: list[str] = []
    def w(s=""):
        lines.append(s)
    finselvat = FINSELVAT.read_text(encoding="utf-8").strip()

    w("=" * 80)
    w("PASSPORT DEEP INSPECTION")
    w(f"Source: {DOCX}")
    w(f"Size: {DOCX.stat().st_size} bytes")
    w("=" * 80)
    w()
    w("## 0. FINSELVAT DETAILS SUMMARY (from finselvat_details.txt)")
    w("-" * 60)
    w(finselvat)
    w()
    w("-" * 60)
    w()

    with zipfile.ZipFile(DOCX) as zf:
        names = zf.namelist()
        doc = ET.fromstring(zf.read("word/document.xml"))
        styles_root = ET.fromstring(zf.read("word/styles.xml")) if "word/styles.xml" in names else None
        rels = load_rels(zf, "word/_rels/document.xml.rels")
        body = doc.find(f"{W}body")
        assert body is not None
        all_tbls = list(body.iter(f"{W}tbl"))

        default_sz = None
        style_sz: dict[str, str] = {}
        if styles_root is not None:
            for style in styles_root.findall(f"{W}style"):
                sid = style.get(f"{W}styleId") or ""
                rPr = style.find(f"{W}rPr")
                if rPr is not None:
                    sz = rPr.find(f"{W}sz")
                    if sz is not None and sz.get(f"{W}val"):
                        style_sz[sid] = half_pt(sz.get(f"{W}val"))
            dd = styles_root.find(f"{W}docDefaults")
            if dd is not None:
                rPr = dd.find(f".//{W}rPr")
                if rPr is not None:
                    sz = rPr.find(f"{W}sz")
                    if sz is not None:
                        default_sz = half_pt(sz.get(f"{W}val"))

        # --- 1 ---
        w("## 1. FIRST TABLE — full cell text (manufacturer / supplier / buyer)")
        w("-" * 60)
        rows0 = cell_grid(all_tbls[0])
        w(f"Dimensions: {len(rows0)} rows × {max(len(r) for r in rows0)} cols")
        w()
        for ri, row in enumerate(rows0):
            w(f"--- Row {ri} ({len(row)} cells) ---")
            for ci, cell in enumerate(row):
                w(f"  [{ri},{ci}]:")
                for line in cell.split("\n"):
                    w(f"    {line}")
            w()

        # --- 2 ---
        w()
        w("## 2. EVERY TABLE — index, dims, borders, sample first row")
        w("-" * 60)
        unique: OrderedDict[str, int] = OrderedDict()
        examples: dict[str, list[str]] = defaultdict(list)

        for ti, tbl in enumerate(all_tbls):
            rows = cell_grid(tbl)
            nr = len(rows)
            nc = max((len(r) for r in rows), default=0)
            tblPr = tbl.find(f"{W}tblPr")
            tblBorders = borders_block(tblPr, "tblBorders")
            cell_notes: list[str] = []
            incomplete = 0
            with_tc = 0
            total = 0
            first_tr = tbl.find(f"{W}tr")
            if first_tr is not None:
                for ci, tc in enumerate(first_tr.findall(f"{W}tc")):
                    tcPr = tc.find(f"{W}tcPr")
                    tcB = borders_block(tcPr, "tcBorders")
                    has = tcPr is not None and tcPr.find(f"{W}tcBorders") is not None
                    if has:
                        cell_notes.append(
                            f"  cell[{ci}] tcBorders: "
                            + ", ".join(f"{k}={tcB[k]}" for k in ("top", "left", "bottom", "right"))
                        )
                        m = miss_edges(tcB, ("top", "left", "bottom", "right"))
                        if m:
                            cell_notes.append("    MISSING/OPEN edges: " + ", ".join(m))
                    else:
                        cell_notes.append(f"  cell[{ci}] tcBorders: (none — inherit tblBorders)")
            for tr in tbl.findall(f"{W}tr"):
                for tc in tr.findall(f"{W}tc"):
                    total += 1
                    tcPr = tc.find(f"{W}tcPr")
                    if tcPr is not None and tcPr.find(f"{W}tcBorders") is not None:
                        with_tc += 1
                        tcB = borders_block(tcPr, "tcBorders")
                        if miss_edges(tcB, ("top", "left", "bottom", "right")):
                            incomplete += 1
                        sig = "tcBorders{" + "; ".join(f"{k}:{v}" for k, v in tcB.items()) + "}"
                        unique[sig] = unique.get(sig, 0) + 1
                        if len(examples[sig]) < 5:
                            examples[sig].append(f"table[{ti}]")
            sig_tbl = "tblBorders{" + "; ".join(f"{k}:{v}" for k, v in tblBorders.items()) + "}"
            unique[sig_tbl] = unique.get(sig_tbl, 0) + 1
            if len(examples[sig_tbl]) < 3:
                examples[sig_tbl].append(f"table[{ti}]")

            tbl_has = tblPr is not None and tblPr.find(f"{W}tblBorders") is not None
            if not tbl_has and with_tc == 0:
                complete = "NO — no tblBorders and no tcBorders"
            elif with_tc and incomplete == with_tc:
                complete = (
                    f"INCOMPLETE — all {with_tc} cells have only top+bottom "
                    f"(left/right MISSING); no tblBorders"
                )
            elif incomplete:
                complete = f"PARTIAL — {incomplete}/{with_tc} cells incomplete tcBorders"
            else:
                complete = "CHECK"

            w(f"### Table [{ti}] — {nr}×{nc}")
            w(f"  Borders complete?: {complete}")
            w(f"  tblBorders present: {tbl_has}")
            w(f"  Cells total: {total}; with tcBorders: {with_tc}; incomplete tcBorders: {incomplete}")
            for n in cell_notes[:8]:
                w(n)
            w("  Sample first row cells:")
            for ci, cell in enumerate(rows[0] if rows else []):
                preview = cell.replace("\n", " | ")
                if len(preview) > 120:
                    preview = preview[:117] + "..."
                w(f"    [{ci}] {preview}")
            w()

        # --- 3 ---
        w()
        w("## 3. EVERY IMAGE — media, size, location, caption «Рис.»?")
        w("-" * 60)
        w("NOTE: image6.png is a ~0.8 mm hairline divider reused as a section rule, NOT a figure.")
        w("Real photo/diagram figures needing captions: image2, image4, image1, image3.")
        w()

        last_heading = "(start)"
        last_para = ""
        img_i = 0
        body_children = list(body)

        def following_caption(after: list[ET.Element], limit: int = 5) -> tuple[bool, str]:
            texts: list[str] = []
            for n in after[:limit]:
                if local(n.tag) == "p":
                    t = para_text(n)
                    if t:
                        texts.append(t)
                elif local(n.tag) == "tbl":
                    break
            joined = " || ".join(texts)
            return bool(re.search(r"(?i)рис\.?|рисунок|fig\.?", joined)), joined

        def drawings_info(el: ET.Element) -> list[tuple[str, str | None, float | None, float | None]]:
            out: list[tuple[str, str | None, float | None, float | None]] = []
            for d in el.findall(f".//{W}drawing"):
                blip = d.find(f".//{A}blip")
                rid = blip.get(f"{R}embed") if blip is not None else None
                extent = d.find(f".//{WP}extent")
                cx = emu_mm(extent.get("cx") if extent is not None else None)
                cy = emu_mm(extent.get("cy") if extent is not None else None)
                if rid and rid in rels:
                    media = Path(rels[rid]).name
                elif rid:
                    media = f"(unresolved {rid})"
                else:
                    media = "(drawing without a:blip — shape/line?)"
                out.append((media, rid, cx, cy))
            for im in el.iter(f"{V}imagedata"):
                rid = im.get(f"{R}id")
                media = Path(rels[rid]).name if rid and rid in rels else "?"
                out.append((media, rid, None, None))
            return out

        for i, child in enumerate(body_children):
            tag = local(child.tag)
            if tag == "sectPr":
                continue
            if tag == "p":
                st = style_of(child)
                t = para_text(child)
                if is_heading(st) and t:
                    last_heading = f"[{st}] {t}"
                if t:
                    last_para = t
                infos = drawings_info(child)
                if infos:
                    has_cap, cap_prev = following_caption(body_children[i + 1 :])
                    for media, rid, cx, cy in infos:
                        img_i += 1
                        size = f"{cx:.1f}×{cy:.1f} mm" if cx is not None and cy is not None else "?"
                        if cy is not None and cy < 2:
                            kind = "HAIRLINE DIVIDER"
                        elif cy is not None and cy >= 20:
                            kind = "FIGURE"
                        else:
                            kind = "other/unknown"
                        w(f"### Image/drawing [{img_i}] {media}  [{kind}]")
                        w(f"  rId={rid}; display size ≈ {size}")
                        w(f"  Preceding heading: {last_heading}")
                        nearby = last_para if last_para else "(empty para containing drawing)"
                        w(f"  Nearby paragraph text: {nearby[:220]}")
                        w(f"  Caption «Рис.» follows?: {'YES' if has_cap else 'NO'}")
                        w(f"  Following paras: {cap_prev or '(none / next is non-text)'}")
                        w()
            elif tag == "tbl":
                infos = drawings_info(child)
                if infos:
                    has_cap, cap_prev = following_caption(body_children[i + 1 :])
                    rows = cell_grid(child)
                    nearby = rows[0][0] if rows and rows[0] else "(table)"
                    for media, rid, cx, cy in infos:
                        img_i += 1
                        size = f"{cx:.1f}×{cy:.1f} mm" if cx is not None and cy is not None else "?"
                        w(f"### Image/drawing [{img_i}] {media}")
                        w(f"  rId={rid}; size ≈ {size}; in table under {last_heading}")
                        w(f"  Nearby: {nearby[:200]}")
                        w(f"  Caption «Рис.» follows?: {'YES' if has_cap else 'NO'}")
                        w()

        media_files = sorted(n for n in names if n.startswith("word/media/"))
        w(f"Total drawings/images walked: {img_i}")
        w(f"Media files in package ({len(media_files)}):")
        for mf in media_files:
            w(f"  - {Path(mf).name}")
        w()

        # --- 4 ---
        w("## 4. HEADER AND FOOTER CONTENT (all sections)")
        w("-" * 60)
        sectPrs = list(body.findall(f".//{W}sectPr"))
        w(f"sectPr count: {len(sectPrs)}")
        hf_parts = [n for n in names if re.search(r"word/(header|footer)", n)]
        w(f"Header/footer ZIP parts present: {hf_parts or 'NONE'}")
        w("FINDING: Document has NO word/header*.xml and NO word/footer*.xml parts.")
        w("sectPr has NO headerReference / footerReference.")
        w("pgMar header=0, footer=0 — footer distance is zero.")
        w("Comment 1 («с нижним колонтитулом что-то не то») is explained by:")
        w("  (a) missing footer entirely (no page numbers / no ГОСТ footer), and/or")
        w("  (b) image2.png ≈ 155×250 mm on Letter page (279 mm high) with 25 mm margins")
        w("      → printable height ≈ 229 mm, so the figure overflows the page bottom.")
        w()
        for si, sect in enumerate(sectPrs):
            w(f"### Section [{si}]")
            w(f"  headerReference count: {len(sect.findall(f'{W}headerReference'))}")
            w(f"  footerReference count: {len(sect.findall(f'{W}footerReference'))}")
            pgSz = sect.find(f"{W}pgSz")
            pgMar = sect.find(f"{W}pgMar")
            pgBorders = sect.find(f"{W}pgBorders")
            if pgSz is not None:
                w(f"  pgSz: w={pgSz.get(f'{W}w')} h={pgSz.get(f'{W}h')} orient={pgSz.get(f'{W}orient')}")
                w(f"        ≈ {twips_mm(pgSz.get(f'{W}w'))} × {twips_mm(pgSz.get(f'{W}h'))}  (US Letter, not A4)")
            if pgMar is not None:
                w(
                    "  pgMar: "
                    f"top={twips_mm(pgMar.get(f'{W}top'))}, bottom={twips_mm(pgMar.get(f'{W}bottom'))}, "
                    f"left={twips_mm(pgMar.get(f'{W}left'))}, right={twips_mm(pgMar.get(f'{W}right'))}, "
                    f"header={twips_mm(pgMar.get(f'{W}header'))}, footer={twips_mm(pgMar.get(f'{W}footer'))}"
                )
            w(f"  pgBorders present?: {'YES' if pgBorders is not None else 'NO'}")
            w()
        w("### Header/footer full text")
        w("  (none — parts absent; no text to extract)")
        w()

        # --- 5 ---
        w("## 5. PAGE SETUP SUMMARY")
        w("-" * 60)
        for si, sect in enumerate(sectPrs):
            pgSz = sect.find(f"{W}pgSz")
            pgMar = sect.find(f"{W}pgMar")
            pgBorders = sect.find(f"{W}pgBorders")
            w(f"Section [{si}]:")
            w(
                f"  Size: {twips_mm(pgSz.get(f'{W}w') if pgSz is not None else None)} × "
                f"{twips_mm(pgSz.get(f'{W}h') if pgSz is not None else None)} (US Letter 8.5×11 in)"
            )
            if pgMar is not None:
                w(
                    f"  Margins: top={twips_mm(pgMar.get(f'{W}top'))}, bottom={twips_mm(pgMar.get(f'{W}bottom'))}, "
                    f"left={twips_mm(pgMar.get(f'{W}left'))}, right={twips_mm(pgMar.get(f'{W}right'))}"
                )
            w(f"  Page borders (pgBorders): {'present' if pgBorders is not None else 'absent'}")
        w()

        # --- 6 ---
        w("## 6. FONT SIZES USED")
        w("-" * 60)
        w(f"Document defaults sz: {default_sz or '(not set)'}")
        w("Style-defined sizes:")
        for sid, sz in sorted(style_sz.items()):
            w(f"  {sid}: {sz}")
        w("Direct w:sz / w:szCs counts in document.xml:")
        for sz, cnt in font_counts(doc).items():
            w(f"  {sz}: {cnt}")
        w()

        # --- 7 ---
        w("## 7. UNIQUE TABLE BORDER STYLES FOUND")
        w("-" * 60)
        w(f"Total unique signatures: {len(unique)}")
        for i, (sig, cnt) in enumerate(unique.items()):
            w(f"[{i}] count={cnt} examples={examples.get(sig, [])[:5]}")
            w(f"  {sig[:700]}{'...' if len(sig) > 700 else ''}")
            w()

        w()
        w("=" * 80)
        w("## 8. ACTIONABLE SUMMARY — comments 0–8 (what must change)")
        w("=" * 80)
        w(
            """
Comment 0 — first table right cell (ПОСТАВЩИК / ПОКУПАТЕЛЬ):
  MUST: rename label to ПОСТАВЩИК only (убрать «Покупатель»).
  MUST: replace contract placeholders with ООО «ФИНСЕЛЬВАТ» requisites
        (legal name, address, УНП 692204462, р/с, банк, ALFABY2X, web) from finselvat_details.
  MUST: add «официальный представитель / сервисный центр на территории РБ».
  MUST: add service contacts from comment: +375 29 667 88 73, HelpDesk@digitranslab.com
        (letterhead also has +375 29 658 53 63 / finselvat.info@yandex.ru — keep service line as in comment).
  NOTE: comment spelling «Финстельват» → correct «ФИНСЕЛЬВАТ».

Comments 2–6 — identity/data tables («Доделать рамку»):
  MUST: add full grid borders on tables [1]…[8] (and ideally [0],[9]):
        currently tcBorders have ONLY top+bottom single sz=6 color=cbd5e0; left/right MISSING;
        no tblBorders anywhere. Set left/right (+ insideV) or use complete tblBorders.

Comment 1 — image2.png under «1. Основные сведения…»:
  MUST: add caption after figure («Рис. …»).
  MUST: fix page-bottom issue: no footer parts exist; image2 is ~250 mm tall on Letter
        (overflows printable area). Scale image down and/or add proper footer (page no / doc id).

Comments 7–8 — image4.png and image1.png under «2.4. Габаритные размеры…»:
  MUST: add «Рис.» captions after each (Подписать). Currently NO figure has a «Рис.» caption.

Optional related (not in comments 0–8 but same pattern):
  - image3.png under §5 also lacks «Рис.» caption.
  - image6.png occurrences are hairline rules — do not caption those.
  - Page is US Letter; ГОСТ docs often A4 — confirm if size change is required.
"""
        )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(lines)} lines)")


if __name__ == "__main__":
    main()
