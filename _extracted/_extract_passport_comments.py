# -*- coding: utf-8 -*-
import zipfile, re, sys, html
from xml.etree import ElementTree as ET
from collections import defaultdict
from pathlib import Path

docx_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

def local(tag):
    return tag.split("}")[-1] if tag and "}" in tag else (tag or "")

def q(ns, name):
    return "{%s}%s" % (NS[ns], name)

def text_of(el):
    parts = []
    for t in el.iter(q("w", "t")):
        if t.text:
            parts.append(t.text)
    return "".join(parts)

def para_text(p):
    return text_of(p).strip()

def attr(el, name):
    for k, v in el.attrib.items():
        if local(k) == name:
            return v
    return None

with zipfile.ZipFile(docx_path, "r") as z:
    names = sorted(z.namelist())
    comment_parts = [n for n in names if ("comment" in n.lower() or n.endswith("people.xml"))]

    def read_xml(name):
        if name not in names:
            return None
        return ET.fromstring(z.read(name))

    comments_root = read_xml("word/comments.xml")
    comments_ext = read_xml("word/commentsExtended.xml")
    comments_ids = read_xml("word/commentsIds.xml")
    document = read_xml("word/document.xml")
    core = read_xml("docProps/core.xml")

    rels = {}
    rels_root = read_xml("word/_rels/document.xml.rels")
    if rels_root is not None:
        for rel in rels_root:
            if local(rel.tag) == "Relationship":
                rels[rel.get("Id")] = rel.get("Target")

    para_parent = {}
    if comments_ext is not None:
        for ce in comments_ext.iter():
            if local(ce.tag) == "commentEx":
                pid = attr(ce, "paraId")
                parent = attr(ce, "paraIdParent")
                if pid and parent:
                    para_parent[pid] = parent

    para_to_durable = {}
    if comments_ids is not None:
        for ci in comments_ids.iter():
            if local(ci.tag) == "commentId":
                pid = attr(ci, "paraId")
                did = attr(ci, "durableId")
                if pid:
                    para_to_durable[pid] = did or ""

    comments = []
    id_to_para = {}
    if comments_root is not None:
        for c in comments_root.findall(q("w", "comment")):
            cid = c.get(q("w", "id"))
            author = c.get(q("w", "author")) or ""
            date = c.get(q("w", "date")) or ""
            initials = c.get(q("w", "initials")) or ""
            body_paras = [para_text(p) for p in c.findall(q("w", "p"))]
            for el in c.iter():
                pid = attr(el, "paraId")
                if pid:
                    id_to_para[cid] = pid
                    break
            body = "\n".join(body_paras).strip()
            comments.append({
                "id": cid,
                "author": author,
                "date": date,
                "initials": initials,
                "body": body,
                "paraId": id_to_para.get(cid),
            })

    para_to_cid = {c["paraId"]: c["id"] for c in comments if c.get("paraId")}

    anchors_text = defaultdict(list)
    anchors_images = defaultdict(list)
    active = set()
    preceding_heading = ""
    comment_context = {}

    if document is not None:
        body = document.find(q("w", "body"))
        if body is not None:
            for el in body.iter():
                tag = local(el.tag)
                if tag == "p":
                    style = ""
                    pPr = el.find(q("w", "pPr"))
                    if pPr is not None:
                        pStyle = pPr.find(q("w", "pStyle"))
                        if pStyle is not None:
                            style = pStyle.get(q("w", "val")) or ""
                    t = para_text(el)
                    if t:
                        st = (style or "").lower()
                        if "heading" in st or "title" in st:
                            preceding_heading = t
                if tag == "commentRangeStart":
                    cid = el.get(q("w", "id"))
                    if cid is not None:
                        active.add(cid)
                        comment_context[cid] = {"preceding_heading": preceding_heading}
                elif tag == "commentRangeEnd":
                    cid = el.get(q("w", "id"))
                    active.discard(cid)
                elif tag == "t" and active and el.text:
                    for cid in list(active):
                        anchors_text[cid].append(el.text)
                elif tag == "docPr" and active:
                    name = el.get("name") or ""
                    for cid in list(active):
                        anchors_images[cid].append(name)

    raw = z.read("word/document.xml").decode("utf-8")
    for c in comments:
        cid = c["id"]
        if not anchors_text.get(cid) and not anchors_images.get(cid):
            m = re.search(
                r'<w:commentRangeStart w:id="%s"/>[\s\S]{0,2500}?<wp:docPr[^>]*name="([^"]+)"' % re.escape(cid),
                raw,
            )
            if m:
                anchors_images[cid].append(m.group(1))
            m2 = re.search(
                r'<w:t[^>]*>([^<]{0,160})</w:t>[\s\S]{0,800}?<w:commentRangeStart w:id="%s"/>' % re.escape(cid),
                raw,
            )
            if m2:
                comment_context.setdefault(cid, {})
                comment_context[cid]["near_text"] = html.unescape(m2.group(1))

    for c in comments:
        pid = c.get("paraId")
        parent_para = para_parent.get(pid) if pid else None
        if parent_para:
            c["parent_id"] = para_to_cid.get(parent_para, "(paraId=%s)" % parent_para)
            c["is_reply"] = True
        else:
            c["parent_id"] = None
            c["is_reply"] = False

    top_level = [c for c in comments if not c["is_reply"]]
    replies = [c for c in comments if c["is_reply"]]
    authors = sorted(set(c["author"] for c in comments))

    top_paras = []
    all_headings = []
    tables_count = 0
    images_count = 0

    def p_style(p):
        pPr = p.find(q("w", "pPr"))
        if pPr is not None:
            pStyle = pPr.find(q("w", "pStyle"))
            if pStyle is not None:
                return pStyle.get(q("w", "val")) or ""
        return ""

    if document is not None:
        body = document.find(q("w", "body"))
        tables_count = len(list(body.iter(q("w", "tbl"))))
        for el in body.iter():
            if local(el.tag) in ("blip", "imagedata"):
                images_count += 1

        def walk(parent, in_tbl=False):
            for child in list(parent):
                tag = local(child.tag)
                if tag == "p":
                    t = para_text(child)
                    if t:
                        style = p_style(child)
                        top_paras.append((style, t, in_tbl))
                        stl = style.lower()
                        if "heading" in stl or stl.startswith("title"):
                            all_headings.append((style, t))
                elif tag == "tbl":
                    for el in child.iter(q("w", "p")):
                        t = para_text(el)
                        if t:
                            style = p_style(el)
                            top_paras.append((style, t, True))
                elif tag == "sdt":
                    for el in child.iter():
                        if local(el.tag) == "sdtContent":
                            walk(el, in_tbl)
                            break
        walk(body)

    first40 = top_paras[:40]
    keywords = re.compile(
        r"finselvat|финселват|производител|поставщик|изготовител|supplier|manufacturer|Предприятие|Изготовитель",
        re.I,
    )
    full_chunks = [t for _, t, _ in top_paras]
    finselvat_hits = [t for t in full_chunks if re.search(r"finselvat|финселват", t, re.I)]
    manuf_hits = []
    seen_m = set()
    for t in full_chunks:
        if keywords.search(t) and t not in seen_m:
            seen_m.add(t)
            manuf_hits.append(t)

    company_lines = []
    for style, t, in_tbl in top_paras:
        if re.search(r"GREWIN|coilwinding|Изготовитель|Предприятие|Поставщик|поставк|Китай|Tianjin|admin@", t, re.I):
            company_lines.append(t)

    xml_finsel = []
    for n in names:
        if not n.endswith(".xml"):
            continue
        rawx = z.read(n).decode("utf-8", errors="ignore")
        if re.search(r"finselvat|финселват", rawx, re.I):
            for m in re.finditer(r".{0,80}(finselvat|финселват).{0,80}", rawx, re.I):
                snippet = re.sub(r"<[^>]+>", " ", m.group(0))
                snippet = re.sub(r"\s+", " ", snippet).strip()
                xml_finsel.append("[%s] %s" % (n, snippet))

    core_info = {}
    if core is not None:
        for child in core:
            core_info[local(child.tag)] = (child.text or "").strip()

    lines = []
    def w(s=""):
        lines.append(s)

    w("=" * 80)
    w("PASSPORT WORD COMMENTS REPORT")
    w("Source: %s" % docx_path)
    w("Size: %s bytes" % docx_path.stat().st_size)
    w("=" * 80)
    w()
    w("## Comment-related ZIP parts")
    for p in comment_parts:
        info = z.getinfo(p)
        w("  - %s  (%s bytes)" % (p, info.file_size))
    w()
    w("## Summary")
    w("  Total comments: %d" % len(comments))
    w("  Top-level comments: %d" % len(top_level))
    w("  Replies: %d" % len(replies))
    w("  Authors (%d): %s" % (len(authors), ", ".join(authors) if authors else "(none)"))
    if core_info:
        w("  Core props: creator=%s; lastModifiedBy=%s; created=%s; modified=%s; title=%s" % (
            core_info.get("creator", ""),
            core_info.get("lastModifiedBy", ""),
            core_info.get("created", ""),
            core_info.get("modified", ""),
            core_info.get("title", ""),
        ))
    w()
    w("## Document structure")
    w("  Tables count: %d" % tables_count)
    w("  Images count (blip/imagedata): %d" % images_count)
    w("  Total non-empty paragraphs walked: %d" % len(top_paras))
    w("  Headings found (by style): %d" % len(all_headings))
    w()
    w("### All headings")
    for i, (style, t) in enumerate(all_headings, 1):
        w("  %d. [%s] %s" % (i, style, t))
    w()
    w("### First 40 non-empty paragraphs")
    for i, (style, t, in_tbl) in enumerate(first40, 1):
        loc = "table" if in_tbl else "body"
        st = (" style=%s" % style) if style else ""
        display = t if len(t) <= 300 else t[:300] + "..."
        w("  %d. (%s%s) %s" % (i, loc, st, display))
    w()
    w("## Manufacturer / supplier / Finselvat text")
    if finselvat_hits:
        w("### Finselvat matches:")
        for t in finselvat_hits:
            w("  - %s" % t)
    else:
        w("### Finselvat matches: (none)")
    if manuf_hits:
        w("### Manufacturer/supplier keyword matches:")
        for t in manuf_hits:
            w("  - %s" % (t if len(t) <= 400 else t[:400] + "..."))
    else:
        w("### Manufacturer/supplier keyword matches: (none)")
    w("### Nearby identity / company lines (context dump):")
    for t in company_lines:
        w("  - %s" % t)
    if xml_finsel:
        w("### Raw XML Finselvat snippets:")
        for t in xml_finsel[:40]:
            w("  - %s" % t)
    else:
        w("### Raw XML Finselvat snippets: (none)")
    w()
    w("=" * 80)
    w("## ALL COMMENTS (detailed)")
    w("=" * 80)
    w()

    def sort_key(c):
        try:
            return int(c["id"])
        except Exception:
            return 0

    for c in sorted(comments, key=sort_key):
        w("-" * 70)
        w("ID: %s" % c["id"])
        w("Author: %s" % c["author"])
        w("Date: %s" % c["date"])
        if c.get("initials"):
            w("Initials: %s" % c["initials"])
        if c.get("paraId"):
            w("ParaId: %s" % c["paraId"])
        durable = para_to_durable.get(c["paraId"]) if c.get("paraId") else None
        if durable:
            w("DurableId: %s" % durable)
        if c["is_reply"]:
            w("Is reply: YES")
            w("Parent comment id: %s" % c["parent_id"])
        else:
            w("Is reply: NO (top-level)")
            w("Parent comment id: (none)")
        text_anchor = "".join(anchors_text.get(c["id"], []))
        imgs = []
        for x in anchors_images.get(c["id"], []):
            if x not in imgs:
                imgs.append(x)
        ctx = comment_context.get(c["id"], {})
        if text_anchor:
            w("ANCHOR text: %s" % text_anchor)
        elif imgs:
            w("ANCHOR text: (no text; comment attached to IMAGE)")
            w("ANCHOR image(s): %s" % ", ".join(imgs))
            if ctx.get("preceding_heading"):
                w("ANCHOR context (preceding heading): %s" % ctx["preceding_heading"])
            if ctx.get("near_text"):
                w("ANCHOR context (near text before marker): %s" % ctx["near_text"])
        else:
            w("ANCHOR text: (empty / point anchor / not found)")
            if ctx.get("preceding_heading"):
                w("ANCHOR context (preceding heading): %s" % ctx["preceding_heading"])
            if ctx.get("near_text"):
                w("ANCHOR context (near text before marker): %s" % ctx["near_text"])
        w("Comment body:")
        w(c["body"] if c["body"] else "(empty)")
        w()

    w("=" * 80)
    w("END OF REPORT")
    w("=" * 80)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", out_path, out_path.stat().st_size)
    print("top", len(top_level), "replies", len(replies))
    for a in authors:
        print("AUTHOR", a.encode("unicode_escape").decode())