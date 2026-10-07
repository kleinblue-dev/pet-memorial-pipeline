# -*- coding: utf-8 -*-
"""qc_all.py — 13 条 I2V 片段批量质检：
数值表（相邻帧差/首帧锚定）+ 两张大拼图（每片 4 帧：0 / 1/3 / 2/3 / 末）
用法: python -X utf8 tools/qc_all.py
"""
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageStat

FF = os.environ.get('FFMPEG', 'ffmpeg')
BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIPS = BASE + '/clips'
VACE = BASE + '/prepped/vace'
OUT = BASE + '/out/qc'
IDS = ['p%02d' % i for i in range(1, 14)]
os.makedirs(OUT, exist_ok=True)

rows, report = [], []
for pid in IDS:
    mp4 = os.path.join(CLIPS, pid + '.mp4')
    src_img = os.path.join(VACE, pid + '_832.jpg')
    tmp = tempfile.mkdtemp(prefix='qc_')
    subprocess.run([FF, '-y', '-hide_banner', '-loglevel', 'error', '-i', mp4,
                    '-fps_mode', 'passthrough', os.path.join(tmp, 'f%03d.png')], check=True)
    files = sorted(os.listdir(tmp))
    imgs = [Image.open(os.path.join(tmp, f)).convert('RGB') for f in files]
    n = len(imgs)
    w, h = imgs[0].size
    small = [im.resize((416, 240), Image.LANCZOS) for im in imgs]
    diffs = [ImageStat.Stat(ImageChops.difference(small[i], small[i + 1])).mean[0]
             for i in range(n - 1)]
    src = Image.open(src_img).convert('RGB').resize((w, h), Image.LANCZOS)

    def md(a, b):
        return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]

    d0 = md(imgs[0], src)
    alls = [md(im, src) for im in imgs]
    bi = alls.index(min(alls))
    amean = sum(diffs) / len(diffs)
    report.append((pid, n, amean, max(diffs), min(diffs), d0, bi))
    picks = [0, n // 3, 2 * n // 3, n - 1]
    rows.append((pid, amean, [imgs[k] for k in picks]))
    shutil.rmtree(tmp, ignore_errors=True)


def sheet(rowset, dst):
    cw, ch, lab = 512, 295, 96
    im = Image.new('RGB', (lab + cw * 4, ch * len(rowset)), (18, 18, 20))
    d = ImageDraw.Draw(im)
    for r, (pid, amean, frames) in enumerate(rowset):
        d.text((8, r * ch + ch // 2 - 16), pid, fill=(255, 240, 180))
        d.text((8, r * ch + ch // 2 + 4), 'diff\n%.2f' % amean, fill=(180, 220, 255))
        for c, f in enumerate(frames):
            im.paste(f.resize((cw, ch), Image.LANCZOS), (lab + c * cw, r * ch))
    im.save(dst)


sheet(rows[:7], OUT + '/sheetA_p01_p07.png')
sheet(rows[7:], OUT + '/sheetB_p08_p13.png')
ok = True
for pid, n, amean, amax, amin, d0, bi in report:
    verdict = 'PASS' if (d0 <= 15 and bi <= 2) else 'FAIL/复核'
    if verdict != 'PASS':
        ok = False
    print('%s n=%d adj mean=%.3f max=%.3f min=%.3f | 帧0diff=%.2f 最像=%d → %s'
          % (pid, n, amean, amax, amin, d0, bi, verdict))
print('QC_ALL=%s' % ('ALL-PASS' if ok else 'HAS-FAIL'))
print('sheets →', OUT + '/sheetA_p01_p07.png', OUT + '/sheetB_p08_p13.png')
