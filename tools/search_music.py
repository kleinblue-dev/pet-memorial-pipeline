# -*- coding: utf-8 -*-
"""search_music.py — 在 Wikimedia Commons 搜安静钢琴曲（公有领域/CC0/CC-BY），列授权+时长候选。"""
import json
import os
import time
import urllib.parse
import urllib.request

PROXY = os.environ.get('FETCH_PROXY', '')   # 例: http://127.0.0.1:7892
_handlers = [urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})] if PROXY else []
opener = urllib.request.build_opener(*_handlers)
opener.addheaders = [('User-Agent', 'PetDemoResearch/1.0 (non-commercial test)')]

QUERIES = ['filetype:audio gymnopedie', 'filetype:audio clair de lune debussy',
           'filetype:audio chopin nocturne op 9', 'filetype:audio piano sad calm']


def get(url):
    for a in range(3):
        try:
            return opener.open(url, timeout=40).read()
        except Exception:
            if a == 2:
                raise
            time.sleep(2)


seen = set()
for q in QUERIES:
    api = ('https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo'
           '&iiprop=url|size|extmetadata|mediatype&generator=search&gsrnamespace=6'
           '&gsrlimit=12&gsrsearch=%s' % urllib.parse.quote(q))
    try:
        d = json.loads(get(api))
    except Exception as e:
        print('[%s] 失败 %s' % (q, e))
        continue
    print('\n== %s ==' % q)
    pages = (d.get('query') or {}).get('pages') or {}
    for p in pages.values():
        ii = (p.get('imageinfo') or [{}])[0]
        md = ii.get('extmetadata') or {}
        lic = (md.get('LicenseShortName') or {}).get('value', '?')
        dur = (md.get('Duration') or {}).get('value', '?')
        title = p.get('title', '')
        if title in seen:
            continue
        seen.add(title)
        print('%-70s | %-22s | %ss | %.0fKB' % (
            title[:70], lic[:22], dur,
            (ii.get('size') or 0) / 1024))
        print('   ', ii.get('url', ''))
    time.sleep(1.2)
