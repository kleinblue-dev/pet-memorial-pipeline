# -*- coding: utf-8 -*-
"""qc_clip.py — 单条 I2V 片段质检：
1) 抽 6 帧拼成帧序条（看动作漂移/鬼畜）
2) 相邻帧差曲线（运动量；太小=没动，太大=跳变）
3) 首帧锚定判定（帧0 应≈输入图）
用法: python -X utf8 tools/qc_clip.py <mp4> <输入图> [输出前缀]
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageStat

FF = os.environ.get('FFMPEG', 'ffmpeg')

mp4, src_img = sys.argv[1], sys.argv[2]
tag = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(mp4))[0]
BASE = os.environ.get('PETDEMO_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
outdir = os.path.join(BASE, 'out', 'qc')
os.makedirs(outdir, exist_ok=True)
tmp = tempfile.mkdtemp(prefix='qcpng_')
subprocess.run([FF, '-y', '-hide_banner', '-loglevel', 'error', '-i', mp4,
                '-fps_mode', 'passthrough', os.path.join(tmp, 'f%03d.png')], check=True)
files = sorted(os.listdir(tmp))
imgs = [Image.open(os.path.join(tmp, f)).convert('RGB') for f in files]
n = len(imgs)
w, h = imgs[0].size
print('frames=%d size=%dx%d' % (n, w, h))

# 1) 帧序条
pick = [0, n // 5, 2 * n // 5, 3 * n // 5, 4 * n // 5, n - 1]
cw = 640
strip = Image.new('RGB', (cw * len(pick), int(h * cw / w)), (20, 20, 22))
for i, k in enumerate(pick):
    im = imgs[k].resize((cw, int(h * cw / w)), Image.LANCZOS)
    strip.paste(im, (i * cw, 0))
d = ImageDraw.Draw(strip)
for i, k in enumerate(pick):
    d.text((i * cw + 6, 6), 'frame %d' % k, fill=(255, 240, 180))
strip.save(os.path.join(outdir, tag + '_strip.png'))

# 2) 相邻帧差
small = [im.resize((416, 240), Image.LANCZOS) for im in imgs]
diffs = [ImageStat.Stat(ImageChops.difference(small[i], small[i + 1])).mean[0]
         for i in range(n - 1)]
diffs_f = [round(x, 3) for x in diffs]
print('adj-diff mean=%.3f min=%.3f max=%.3f' % (sum(diffs) / len(diffs), min(diffs), max(diffs)))
print('adj-diff 序列:', diffs_f)

# 3) 首帧锚定
src = Image.open(src_img).convert('RGB').resize((w, h), Image.LANCZOS)
def md(a, b):
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
d0, dm, dz = md(imgs[0], src), md(imgs[n // 2], src), md(imgs[-1], src)
alls = [md(im, src) for im in imgs]
bi = alls.index(min(alls))
print('meandiff 帧0=%.2f 中帧=%.2f 末帧=%.2f 最像=%d' % (d0, dm, dz, bi))
print('首帧锚定: %s' % ('PASS' if d0 <= 15 and bi <= 2 else 'FAIL/复核'))
print('strip →', os.path.join(outdir, tag + '_strip.png'))
