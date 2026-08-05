import zipfile, sys, re
from pathlib import Path
from xml.etree import ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')

p = Path(r'c:\Users\user\Desktop\666\TZ-unified-v1.5 (МИХ).docx')
out_path = Path(r'C:\Users\user\Desktop\sufler\sufler\_tmp_table_261_comments.txt')
z = zipfile.ZipFile(p)
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
comments = {}
root = ET.fromstring(z.read('word/comments.xml'))
for c in root.findall(f'{W}comment'):
    cid = c.get(f'{W}id')
    author = c.get(f'{W}author','')
    text = ''.join(t.text or '' for t in c.findall(f'.//{W}t'))
    comments[cid] = (author, text)

doc = ET.fromstring(z.read('word/document.xml'))
body = doc.find(f'{W}body')
comment_contexts = {cid: [] for cid in comments}
active = set()
para_texts = []
for p_el in body.iter(f'{W}p'):
    texts = []
    for node in p_el.iter():
        if node.tag == f'{W}commentRangeStart':
            active.add(node.get(f'{W}id'))
        elif node.tag == f'{W}commentRangeEnd':
            active.discard(node.get(f'{W}id'))
        elif node.tag == f'{W}t' and node.text:
            texts.append(node.text)
    text = ''.join(texts).strip()
    if text:
        para_texts.append(text)
        for cid in active:
            if len(comment_contexts[cid]) < 6:
                comment_contexts[cid].append(text[:300])
    for cref in p_el.findall(f'.//{W}commentReference'):
        cid = cref.get(f'{W}id')
        if cid and text and len(comment_contexts[cid]) < 6:
            comment_contexts[cid].append('REF:'+text[:300])

lines = []
lines.append(f'FILE exists={p.exists()} size={p.stat().st_size} comments={len(comments)} paras={len(para_texts)}')

# Find II.6.1 / FR-RPT section indices
for i,t in enumerate(para_texts):
    if 'II.6.1' in t or 'II.6' in t and 'отчет' in t.lower():
        lines.append(f'HDR {i}: {t[:250]}')
    if re.search(r'FR-RPT-CC-\d+', t) and len(t)<40:
        lines.append(f'ROW {i}: {t}')

# Dump FR-RPT table area (from first FR-RPT-CC-01 to after last FR-RPT)
start=None
end=None
for i,t in enumerate(para_texts):
    if t.startswith('FR-RPT-CC-01'):
        start=i-5
    if t.startswith('FR-RPT-CC-15'):
        end=i+40
if start is not None:
    lines.append('\n===== TABLE AREA =====')
    for i in range(max(0,start), min(len(para_texts), end or start+200)):
        lines.append(f'{i}|{para_texts[i][:400]}')

# Also find text block about reports before/after table that says "перенести"
lines.append('\n===== ALL COMMENTS with reporting keywords or FR-RPT context =====')
for cid, (author, text) in sorted(comments.items(), key=lambda x: int(x[0])):
    ctx = ' | '.join(comment_contexts.get(cid, []))
    blob = (text+' '+ctx).lower()
    keys = ['отчет','отчёт','fr-rpt','4.7','таблиц','реализац','описан','aht','уведом','релевант','полезн','дашборд','производитель','задерж','порог','chat-t-14','uc-rep','не простав','xlsx','конструктор','закономер','монитор','перенести','формул','ii.6']
    if any(k in blob for k in keys):
        # keep if clearly about this table area
        if any(x in ctx for x in ['FR-RPT','4.7','II.6','отчет','релевант','дашборд','производитель','AHT','CHAT-T','UC-REP','конструктор','закономер','xlsx','полезн','монитор','Перенести','перенести']) or any(k in text.lower() for k in ['отчет','отчёт','aht','порог','задерж','уведом','описан','реализац','таблиц','перенести','4.7','ii.6','формул','xlsx']):
            lines.append(f'\n--- ID={cid} ({author}) ---')
            lines.append('COMMENT: '+text)
            lines.append('CTX: '+ctx[:800])

# Also dump paragraphs containing 4.7 after table (narrative that should move into table)
lines.append('\n===== PARAS with 4.7 near reporting (search) =====')
for i,t in enumerate(para_texts):
    if '4.7.' in t or (t.startswith('4.7')):
        if 0 <= i:
            # only around reporting section - find by proximity to FR-RPT or II.6
            pass
# find II.6 section range
ii6=None
for i,t in enumerate(para_texts):
    if 'II.6' in t:
        ii6=i
        lines.append(f'II6_AT {i}: {t[:200]}')
if ii6:
    for i in range(ii6, min(len(para_texts), ii6+400)):
        if para_texts[i].startswith('II.7') or para_texts[i].startswith('III.') or 'III.1' in para_texts[i][:20]:
            lines.append(f'END_SECTION {i}: {para_texts[i][:100]}')
            break
        lines.append(f'{i}|{para_texts[i][:500]}')

out = '\n'.join(lines)
out_path.write_text(out, encoding='utf-8')
print(out[:15000])
print('\n... wrote', out_path, 'chars', len(out))
