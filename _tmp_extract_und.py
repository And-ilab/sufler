# -*- coding: utf-8 -*-
import re, sys, xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

base = Path(r'C:\Users\user\Desktop\sufler\sufler\_tmp_und_extract\word')
dump_path = Path(r'C:\Users\user\Desktop\sufler\sufler\_tmp_und_section.txt')
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W_ID = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id'
W_AUTHOR = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author'
W_DATE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date'
W_P = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'
W_T = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'

def para_text(p):
    return ''.join(t.text or '' for t in p.iter(W_T))

summary = []
lines = []
lines.append('TZ-unified-v1.5 (МИХ).docx — UC-UND / II.2 context dump')
lines.append('')

# --- 1) Comments ---
print('='*60)
print('1) COMMENTS matching UC-UND / понимания запросов')
print('='*60)
summary.append('1) COMMENTS')
ctree = ET.parse(base/'comments.xml')
croot = ctree.getroot()
comments = list(croot.findall('w:comment', NS))
matched_comments = []
for c in comments:
    cid, author, date = c.get(W_ID), c.get(W_AUTHOR), c.get(W_DATE)
    texts = [para_text(p) for p in c.findall('.//w:p', NS)]
    texts = [t for t in texts if t.strip()]
    full = '\n'.join(texts)
    if re.search(r'UC-UND|понимания запросов', full, re.I):
        matched_comments.append((cid, author, date, full))
        print(f'ID: {cid}')
        print(f'Author: {author}')
        print(f'Date: {date}')
        print(f'Text:\n{full}')
        print('-'*40)
        summary.append(f'  ID={cid} author={author}')
        summary.append(f'  text={full.replace(chr(10), " | ")}')

print(f'Total comments: {len(comments)}; Matched: {len(matched_comments)}')
summary.append(f'Total comments: {len(comments)}; Matched: {len(matched_comments)}')

lines.append('=== MATCHED COMMENTS ===')
for cid, author, date, full in matched_comments:
    lines += [f'ID: {cid}', f'Author: {author}', f'Date: {date}', f'Text:\n{full}', '-'*40]

# --- 4) UC-UND-01 anywhere ---
print('\n'+'='*60)
print('4) UC-UND-01 / UC-UND anywhere under word/')
print('='*60)
summary.append('4) UC-UND-01 presence')
found = []
for f in sorted(base.rglob('*')):
    if not f.is_file() or f.suffix.lower() not in {'.xml', '.rels'}:
        continue
    raw = f.read_text(encoding='utf-8', errors='ignore')
    if 'UC-UND' in raw:
        c01 = raw.count('UC-UND-01')
        ids = sorted(set(re.findall(r'UC-UND-\d+', raw)))
        found.append((str(f.relative_to(base)), c01, ids))
        print(f'{f.relative_to(base)}: UC-UND-01={c01}; IDs={ids}')
        summary.append(f'  {f.relative_to(base)}: UC-UND-01={c01}; IDs={ids}')

# --- 2) document paragraphs ---
print('\n'+'='*60)
print('2) document.xml paragraph hits')
print('='*60)
summary.append('2) document.xml hits')
droot = ET.parse(base/'document.xml').getroot()
body = droot.find('w:body', NS)
paras = list(body.iter(W_P))
para_texts = [para_text(p) for p in paras]
print(f'Total paragraphs: {len(para_texts)}')

patterns = [
    (r'UC-UND', 'UC-UND'),
    (r'FR-UND', 'FR-UND'),
    (r'II\.2', 'II.2'),
    (r'Модуль понимания', 'Модуль понимания'),
]
hits = {k: [] for _, k in patterns}
for i, t in enumerate(para_texts):
    if not t.strip():
        continue
    for pat, key in patterns:
        if re.search(pat, t):
            hits[key].append((i, t))

for key in hits:
    print(f'\n--- {key}: {len(hits[key])} paragraphs ---')
    summary.append(f'  {key}: {len(hits[key])} paragraphs')
    for i, t in hits[key][:25]:
        preview = t if len(t) <= 220 else t[:220] + '...'
        print(f'[{i}] {preview}')
    if len(hits[key]) > 25:
        print(f'... and {len(hits[key])-25} more')

lines.append('')
lines.append('=== DOCUMENT PARAGRAPH HITS ===')
for key in hits:
    lines.append(f'\n--- {key}: {len(hits[key])} ---')
    for i, t in hits[key]:
        lines.append(f'[{i}] {t}')

# --- 3) II.2 section ---
print('\n'+'='*60)
print('3) Section II.2 until II.3')
print('='*60)
summary.append('3) II.2 section')

start_idx = None
end_idx = None
for i, t in enumerate(para_texts):
    s = t.strip()
    if re.match(r'^II\.2(\b|[\s.]|$)', s):
        start_idx = i
        print(f'Start [{i}]: {s[:200]}')
        summary.append(f'  start[{i}]={s[:120]}')
        break

if start_idx is not None:
    for i in range(start_idx + 1, len(para_texts)):
        s = para_texts[i].strip()
        if re.match(r'^II\.3(\b|[\s.]|$)', s):
            end_idx = i
            print(f'End [{i}]: {s[:200]}')
            summary.append(f'  end[{i}]={s[:120]}')
            break

lines.append('')
lines.append('=== SECTION II.2 until II.3 ===')
if start_idx is None:
    print('II.2 START NOT FOUND — listing II.* headings')
    summary.append('  II.2 START NOT FOUND')
    lines.append('II.2 section START NOT FOUND')
    for i, t in enumerate(para_texts):
        s = t.strip()
        if re.match(r'^II\.\d+', s):
            print(f'[{i}] {s[:150]}')
            lines.append(f'HEADING [{i}] {s}')
else:
    end = end_idx if end_idx is not None else min(start_idx + 300, len(para_texts))
    print(f'Dumping paras [{start_idx} .. {end}) count={end - start_idx}')
    summary.append(f'  dumped [{start_idx}..{end}) count={end-start_idx}')
    lines.append(f'Range: [{start_idx} .. {end}) end_exclusive; II.3_at={end_idx}')
    lines.append('')
    nonempty = 0
    for i in range(start_idx, end):
        t = para_texts[i]
        if t.strip():
            lines.append(f'[{i}] {t}')
            nonempty += 1
    print(f'Non-empty paragraphs in section: {nonempty}')

# Also note comment range anchors for comment 1720 if present
print('\n'+'='*60)
print('Comment range anchors for matched IDs (document.xml)')
print('='*60)
doc_raw = (base/'document.xml').read_text(encoding='utf-8', errors='ignore')
for cid, author, date, full in matched_comments:
    # find commentRangeStart/End and commentReference
    for m in re.finditer(rf'w:commentRangeStart[^>]*w:id="{cid}"', doc_raw):
        print(f'commentRangeStart id={cid} at offset {m.start()}')
    for m in re.finditer(rf'w:commentRangeEnd[^>]*w:id="{cid}"', doc_raw):
        print(f'commentRangeEnd id={cid} at offset {m.start()}')
    # find nearby text: extract ~400 chars after start
    m = re.search(rf'<w:commentRangeStart[^>]*w:id="{cid}"[^/]*/>', doc_raw)
    if m:
        snippet = doc_raw[m.start(): m.start()+2500]
        texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', snippet)
        joined = ''.join(texts)
        print(f'Anchored text near comment {cid}: {joined[:400]}')
        summary.append(f'  comment {cid} anchored text: {joined[:200]}')
        lines.append('')
        lines.append(f'=== COMMENT {cid} ANCHOR TEXT ===')
        lines.append(joined[:1000])

dump_path.write_text('\n'.join(lines), encoding='utf-8')
print(f'\nWrote dump: {dump_path} ({dump_path.stat().st_size} bytes)')

print('\n'+'='*60)
print('FINDINGS SUMMARY')
print('='*60)
for s in summary:
    print(s)
