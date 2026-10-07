# -*- coding: utf-8 -*-
"""fetch_photos.py — 阶段①素材采集：Openverse API（license=cc0,pdm 只取无限制授权）
下载候选宠物照片 → src/raw/ + meta_photos.json（含来源/授权/作者，留痕）。
"""
import json
import os
import time
import urllib.parse
import urllib.request

PROXY = os.environ.get('FETCH_PROXY', '')   # 例: http://127.0.0.1:7892（境外站点有时需要）
BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = BASE + '/src/raw'
os.makedirs(RAW, exist_ok=True)

_handlers = [urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})] if PROXY else []
opener = urllib.request.build_opener(*_handlers)
opener.addheaders = [('User-Agent', 'PetDemoResearch/1.0 (non-commercial test)')]

QUERIES = [
    ('q1', 'golden retriever'),
    ('q2', 'golden retriever puppy'),
    ('q3', 'golden retriever sleeping'),
    ('q4', 'golden retriever portrait'),
    ('q5', 'golden retriever dog beach'),
    ('q6', 'old dog photograph vintage'),
]

def get(url, timeout=40):
    for a in range(3):
        try:
            return opener.open(url, timeout=timeout).read()
        except Exception as e:
            if a == 2:
                raise
            time.sleep(2)

t0 = time.time()
cands = {}
for tag, q in QUERIES:
    api = ('https://api.openverse.org/v1/images/?q=%s&license=cc0,pdm&page_size=20'
           '&mature=false' % urllib.parse.quote(q))
    try:
        data = json.loads(get(api))
    except Exception as e:
        print('[%s] API 失败: %s' % (tag, e), flush=True)
        continue
    n = 0
    for r in data.get('results', []):
        u = r.get('url') or ''
        if not u.lower().split('?')[0].endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
        if u in cands:
            continue
        w, h = r.get('width') or 0, r.get('height') or 0
        cands[u] = {'q': tag, 'id': r.get('id'), 'title': r.get('title'),
                    'url': u, 'w': w, 'h': h, 'license': r.get('license'),
                    'creator': r.get('creator'), 'landing': r.get('foreign_landing_url'),
                    'source': r.get('source')}
        n += 1
    print('[%s] %-32s → %d 条候选' % (tag, q, n), flush=True)
    time.sleep(1.2)

print('候选总数:', len(cands), flush=True)

# 挑选：优先宽≥1000 且比例正常；另挑几张宽≤800 的小图（修复演示用）
big = [c for c in cands.values() if c['w'] >= 1000 and c['h'] and 0.45 <= c['w'] / c['h'] <= 2.4]
small = [c for c in cands.values() if 250 <= c['w'] <= 800 and c['h'] and 0.45 <= c['w'] / c['h'] <= 2.4]
big.sort(key=lambda c: -(c['w'] * c['h']))
small.sort(key=lambda c: -(c['w'] * c['h']))
picked, seen_q = [], {}
for c in big:
    if seen_q.get(c['q'], 0) >= 8:
        continue
    picked.append(c)
    seen_q[c['q']] = seen_q.get(c['q'], 0) + 1

meta = []
for i, c in enumerate(picked[:44], 1):
    ext = os.path.splitext(c['url'].split('?')[0])[1].lower() or '.jpg'
    fn = 'big_%02d%s' % (i, ext)
    path = os.path.join(RAW, fn)
    try:
        blob = get(c['url'])
        if len(blob) < 8000:
            print('  跳过(太小 %dB): %s' % (len(blob), fn), flush=True)
            continue
        with open(path, 'wb') as f:
            f.write(blob)
        rec = dict(c); rec['file'] = fn; rec['bytes'] = len(blob)
        meta.append(rec)
        print('  ↓ %s (%dx%d, %.0fKB, %s)' % (fn, c['w'], c['h'], len(blob) / 1024, c['license']), flush=True)
    except Exception as e:
        print('  下载失败 %s: %s' % (fn, e), flush=True)
    time.sleep(0.4)

for i, c in enumerate(small[:6], 1):
    ext = os.path.splitext(c['url'].split('?')[0])[1].lower() or '.jpg'
    fn = 'small_%02d%s' % (i, ext)
    path = os.path.join(RAW, fn)
    try:
        blob = get(c['url'])
        with open(path, 'wb') as f:
            f.write(blob)
        rec = dict(c); rec['file'] = fn; rec['bytes'] = len(blob); rec['tier'] = 'small'
        meta.append(rec)
        print('  ↓ %s (%dx%d, %.0fKB, %s) [小图]' % (fn, c['w'], c['h'], len(blob) / 1024, c['license']), flush=True)
    except Exception as e:
        print('  下载失败 %s: %s' % (fn, e), flush=True)
    time.sleep(0.4)

with open(BASE + '/src/meta_photos.json', 'w', encoding='utf-8') as f:
    json.dump({'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'n': len(meta),
               'elapsed_sec': round(time.time() - t0, 1), 'items': meta},
              f, ensure_ascii=False, indent=1)
print('== 完成 %d 张，用时 %.0fs ==' % (len(meta), time.time() - t0), flush=True)
