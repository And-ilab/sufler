# -*- coding: utf-8 -*-
from pathlib import Path
import zipfile, re, shutil, io
from xml.etree import ElementTree as ET
from collections import OrderedDict

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}

out_dir = Path(r'C:\Users\user\Desktop\sufler\sufler\_extracted')
figs_dir = out_dir / 'manual_figures'
figs_dir.mkdir(parents=True, exist_ok=True)
home = Path.home()

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def docx_paragraphs(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(W + 'p'):
        texts = []
        for t in p.iter(W + 't'):
            if t.text:
                texts.append(t.text)
            if t.tail:
                texts.append(t.tail)
        paras.append(''.join(texts))
    return paras

def docx_full_text(docx_path):
    return '\n'.join(docx_paragraphs(docx_path))

# ========== 1. PASSPORT MANUFACTURER ==========
passports = []
for base in [home/'Desktop', home/'Downloads']:
    for p in base.glob('*.docx'):
        if 'GW-DS09' in p.name and 'аспорт' in p.name.lower() or ('GW-DS09' in p.name and p.suffix=='.docx' and '\u041f\u0430\u0441\u043f\u043e\u0440\u0442' in p.name):
            passports.append(p)
# safer: any GW-DS09 docx that looks like passport
passports = []
for base in [home/'Desktop', home/'Downloads']:
    for p in base.glob('*.docx'):
        if 'GW-DS09' in p.name and 'Double' not in p.name:
            passports.append(p)
passports = sorted(set(passports), key=lambda p: p.stat().st_mtime, reverse=True)
passport = passports[0] if passports else None

mfg_lines = []
if passport:
    mfg_lines.append(f'Source: {passport}')
    mfg_lines.append(f'Source name: {passport.name}')
    mfg_lines.append('')
    paras = docx_paragraphs(passport)
    mfg_lines.append('=== Full document text (paragraphs) ===')
    for i, t in enumerate(paras):
        if t.strip():
            mfg_lines.append(f'[{i}] {t}')
    # Heuristic extract
    text = '\n'.join(paras)
    mfg_lines.append('')
    mfg_lines.append('=== Heuristic company/address hits ===')
    keys = re.compile(r'изготовител|производител|завод|адрес|компани|ООО|АО|Ltd|Co\.|Manufacturer|Address|China|Китай|Guang|Zhejiang|Jiangsu|Shanghai|factory|Factory|UNP|УНП|тел|phone|email|@', re.I)
    for i, t in enumerate(paras):
        if keys.search(t):
            mfg_lines.append(f'[{i}] {t}')
else:
    mfg_lines.append('NOT FOUND: GW-DS09 passport docx')

(out_dir / 'passport_manufacturer.txt').write_text('\n'.join(mfg_lines), encoding='utf-8')
print('Wrote passport_manufacturer.txt, source=', passport)

# ========== 2. FINSELVAT ==========
fin_lines = []
fin_lines.append('Search terms: Финсельват, Finselvat, Финсель')
fin_lines.append('Search roots: Desktop, Downloads, Documents, sufler project')
fin_lines.append('')
pat = re.compile(r'Финсельват|Finselvat|Финсель', re.I)
hits = []
bases = [home/'Desktop', home/'Downloads', home/'Documents', Path(r'C:\Users\user\Desktop\sufler\sufler')]
text_exts = {'.md', '.txt', '.json', '.csv', '.xml', '.html', '.py', '.yml', '.yaml', '.log'}
bin_exts = {'.docx', '.pdf', '.xlsx'}

for base in bases:
    if not base.exists():
        continue
    for p in base.rglob('*'):
        if not p.is_file():
            continue
        # skip huge / node / venv
        parts = set(p.parts)
        if any(x in parts for x in {'node_modules', '.git', 'venv', '.venv', '__pycache__', 'tz_v14_edit'}):
            continue
        try:
            if pat.search(p.name):
                hits.append(('filename', str(p), ''))
        except Exception:
            pass
        suf = p.suffix.lower()
        if suf in text_exts:
            try:
                if p.stat().st_size > 5_000_000:
                    continue
                content = p.read_text(encoding='utf-8', errors='ignore')
                for mi, line in enumerate(content.splitlines(), 1):
                    if pat.search(line):
                        hits.append(('text', str(p), f'L{mi}: {line.strip()[:300]}'))
            except Exception:
                pass
        elif suf == '.docx':
            try:
                if p.stat().st_size > 30_000_000:
                    continue
                # only search name-likely or small docs; always try if under 5MB or name match
                if p.stat().st_size > 8_000_000 and not pat.search(p.name):
                    # still search key folders
                    if 'sufler' not in str(p).lower() and base.name not in ('Desktop', 'Downloads', 'Documents'):
                        continue
                with zipfile.ZipFile(p) as z:
                    names = z.namelist()
                    chunks = []
                    if 'word/document.xml' in names:
                        chunks.append(z.read('word/document.xml').decode('utf-8', errors='ignore'))
                    for n in names:
                        if 'comment' in n.lower() and n.endswith('.xml'):
                            chunks.append(z.read(n).decode('utf-8', errors='ignore'))
                    blob = '\n'.join(chunks)
                    # strip tags roughly for readability
                    if pat.search(blob):
                        plain = re.sub(r'<[^>]+>', ' ', blob)
                        plain = re.sub(r'\s+', ' ', plain)
                        for m in pat.finditer(plain):
                            start = max(0, m.start()-120)
                            end = min(len(plain), m.end()+200)
                            hits.append(('docx', str(p), plain[start:end]))
                            break
            except Exception as e:
                pass
        elif suf == '.pdf':
            # try raw strings
            try:
                if p.stat().st_size > 15_000_000:
                    continue
                raw = p.read_bytes()
                # latin/utf8 attempts
                for enc in ('utf-8', 'cp1251', 'latin-1'):
                    try:
                        s = raw.decode(enc, errors='ignore')
                    except Exception:
                        continue
                    if pat.search(s):
                        hits.append(('pdf-raw', str(p), 'pattern found in raw PDF bytes (may need manual open)'))
                        break
            except Exception:
                pass
        elif suf == '.xlsx':
            try:
                if p.stat().st_size > 10_000_000:
                    continue
                with zipfile.ZipFile(p) as z:
                    blob = ''
                    for n in z.namelist():
                        if n.startswith('xl/') and n.endswith('.xml'):
                            blob += z.read(n).decode('utf-8', errors='ignore')
                    if pat.search(blob):
                        plain = re.sub(r'<[^>]+>', ' ', blob)
                        plain = re.sub(r'\s+', ' ', plain)
                        for m in pat.finditer(plain):
                            start = max(0, m.start()-80)
                            end = min(len(plain), m.end()+160)
                            hits.append(('xlsx', str(p), plain[start:end]))
                            break
            except Exception:
                pass

# Dedup
seen = set()
uniq = []
for h in hits:
    key = (h[0], h[1], h[2][:80])
    if key in seen:
        continue
    seen.add(key)
    uniq.append(h)

fin_lines.append(f'Total unique hits: {len(uniq)}')
fin_lines.append('')
if not uniq:
    fin_lines.append('NOT FOUND: No files containing Финсельват / Finselvat / Финсель with address, UNP, phone, email, or bank details.')
    fin_lines.append('Only known references are project comments requesting to insert ООО "Финсельват" as RB supplier/representative/service center, without providing реквизиты.')
else:
    for kind, path, snippet in uniq:
        fin_lines.append(f'--- [{kind}] {path}')
        if snippet:
            fin_lines.append(f'    {snippet}')
        fin_lines.append('')
    # Check if any hit has address/UNP/bank
    detail_re = re.compile(r'УНП|UNP|р/с|расчетн|банк|IBAN|БИК|адрес|тел\.|телефон|\+375|@|email|e-mail', re.I)
    has_details = any(detail_re.search(h[2]) for h in uniq if h[2])
    fin_lines.append('')
    if has_details:
        fin_lines.append('DETAIL EXTRACTION: possible address/UNP/phone/email/bank found in snippets above — review manually.')
    else:
        fin_lines.append('DETAIL EXTRACTION: hits found but NO address, UNP, phone, email, or bank details present in matched content.')
        fin_lines.append('Known mention: ООО "Финсельват" as поставщик / официальный представитель в РБ / сервисный центр в РБ (from manual Word comments only).')

(out_dir / 'finselvat_details.txt').write_text('\n'.join(fin_lines), encoding='utf-8')
print('Wrote finselvat_details.txt, hits=', len(uniq))

# ========== 4. TITLE YEAR + 5. FONTS (manual) ==========
manual = Path(r'c:\Users\user\Downloads\Rukovodstvo_po_ekspluatacii_dvuhstancionnaya_namotochnaya_mashina1.docx')

def get_align(pPr):
    if pPr is None:
        return 'None (default left/both)'
    jc = pPr.find(W+'jc')
    if jc is not None:
        return jc.get(W+'val')
    return 'None (default)'

def get_spacing(pPr):
    if pPr is None:
        return {}
    sp = pPr.find(W+'spacing')
    if sp is None:
        return {}
    return {k.replace(W,''): v for k,v in sp.attrib.items()}

year_lines = []
font_sizes = set()
if manual.exists():
    with zipfile.ZipFile(manual) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    body = root.find(W+'body')
    paras = list(body.iter(W+'p')) if body is not None else list(root.iter(W+'p'))
    # Also direct children of body for true paragraph index
    body_paras = [c for c in list(body) if c.tag == W+'p'] if body is not None else []

    year_lines.append(f'Source: {manual}')
    year_lines.append(f'Total body direct paragraphs: {len(body_paras)}')
    year_lines.append('')
    year_lines.append('=== Title page context (first ~40 non-empty paragraphs) ===')

    for idx, p in enumerate(body_paras):
        texts = []
        for t in p.iter(W+'t'):
            if t.text:
                texts.append(t.text)
        text = ''.join(texts)
        pPr = p.find(W+'pPr')
        align = get_align(pPr)
        spacing = get_spacing(pPr)
        # font sizes in this para
        szs = []
        for r in p.iter(W+'r'):
            rPr = r.find(W+'rPr')
            if rPr is not None:
                sz = rPr.find(W+'sz')
                if sz is not None:
                    half = sz.get(W+'val')
                    if half:
                        font_sizes.add(int(half))
                        szs.append(half)
                szCs = rPr.find(W+'szCs')
                if szCs is not None:
                    half = szCs.get(W+'val')
                    if half:
                        font_sizes.add(int(half))
        if idx < 50 or '2026' in text:
            if text.strip() or '2026' in text:
                year_lines.append(f'p[{idx}] align={align} spacing={spacing} sz={szs} text={text!r}')

    year_lines.append('')
    year_lines.append('=== Paragraphs containing 2026 ===')
    for idx, p in enumerate(body_paras):
        texts = []
        for t in p.iter(W+'t'):
            if t.text:
                texts.append(t.text)
        text = ''.join(texts)
        if '2026' not in text:
            continue
        pPr = p.find(W+'pPr')
        align = get_align(pPr)
        spacing = get_spacing(pPr)
        # Also check sectPr / frame / position
        year_lines.append(f'Paragraph index (0-based among body <w:p>): {idx}')
        year_lines.append(f'Text: {text!r}')
        year_lines.append(f'Alignment (w:jc): {align}')
        year_lines.append(f'Spacing (w:spacing attrs): {spacing}')
        # before/after in twips (1/20 pt); also check ind
        if pPr is not None:
            ind = pPr.find(W+'ind')
            if ind is not None:
                year_lines.append(f'Indent: { {k.replace(W,""):v for k,v in ind.attrib.items()} }')
            # look for spacing before/after interpretation
            sp = pPr.find(W+'spacing')
            if sp is not None:
                before = sp.get(W+'before')
                after = sp.get(W+'after')
                beforeLines = sp.get(W+'beforeLines')
                afterLines = sp.get(W+'afterLines')
                line = sp.get(W+'line')
                lineRule = sp.get(W+'lineRule')
                year_lines.append(f'spacing before (twips): {before}')
                year_lines.append(f'spacing after (twips): {after}')
                year_lines.append(f'spacing beforeLines: {beforeLines}')
                year_lines.append(f'spacing afterLines: {afterLines}')
                year_lines.append(f'line: {line} lineRule: {lineRule}')
                if before:
                    year_lines.append(f'  before ≈ {int(before)/20:.1f} pt')
                if after:
                    year_lines.append(f'  after ≈ {int(after)/20:.1f} pt')
            else:
                year_lines.append('No w:spacing element on this paragraph.')
        else:
            year_lines.append('No w:pPr on this paragraph.')
        # run props
        for ri, r in enumerate(p.iter(W+'r')):
            rPr = r.find(W+'rPr')
            rtext = ''.join((t.text or '') for t in r.iter(W+'t'))
            if not rtext.strip() and '2026' not in rtext:
                continue
            info = {'text': rtext}
            if rPr is not None:
                sz = rPr.find(W+'sz')
                if sz is not None:
                    info['sz_half_points'] = sz.get(W+'val')
                    info['sz_pt'] = int(sz.get(W+'val'))/2 if sz.get(W+'val') else None
                rFonts = rPr.find(W+'rFonts')
                if rFonts is not None:
                    info['fonts'] = {k.replace(W,''):v for k,v in rFonts.attrib.items()}
            year_lines.append(f'  run[{ri}]: {info}')
        year_lines.append('')

    # Also scan ALL sz in document
    for sz in root.iter(W+'sz'):
        v = sz.get(W+'val')
        if v:
            font_sizes.add(int(v))
    for sz in root.iter(W+'szCs'):
        v = sz.get(W+'val')
        if v:
            font_sizes.add(int(v))

    # styles.xml defaults
    with zipfile.ZipFile(manual) as z:
        if 'word/styles.xml' in z.namelist():
            sroot = ET.fromstring(z.read('word/styles.xml'))
            for sz in sroot.iter(W+'sz'):
                v = sz.get(W+'val')
                if v:
                    font_sizes.add(int(v))
else:
    year_lines.append('Manual not found')

(out_dir / 'manual_title_year.txt').write_text('\n'.join(year_lines), encoding='utf-8')

font_lines = []
font_lines.append(f'Source: {manual}')
font_lines.append('Values are w:sz half-points (divide by 2 for pt).')
font_lines.append('')
uniq_sz = sorted(font_sizes)
font_lines.append('Unique w:sz / w:szCs values (half-points): ' + ', '.join(str(x) for x in uniq_sz))
font_lines.append('Unique sizes in points: ' + ', '.join(f'{x/2:g}' for x in uniq_sz))
font_lines.append('')
font_lines.append('Table:')
font_lines.append('half-points | points')
for x in uniq_sz:
    font_lines.append(f'{x} | {x/2:g}')
(out_dir / 'manual_fonts.txt').write_text('\n'.join(font_lines), encoding='utf-8')
print('Wrote manual_title_year.txt and manual_fonts.txt')
print('Font sizes half-pt:', uniq_sz)
